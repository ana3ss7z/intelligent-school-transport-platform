import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import '../config/env.dart';
import '../models/models.dart';

/// Nature d'une écriture différée.
enum OutboxKind {
  presence,
  trajetDemarrer,
  trajetTerminer,
  incident,
  message,
  diffusion,
}

/// Une écriture en attente d'être envoyée au backend.
class OutboxItem {
  final String id;
  final OutboxKind kind;
  final Map<String, dynamic> payload;
  final DateTime createdAt;
  int attempts;
  String? lastError;

  /// Plafond d'essais atteint : l'item ne repart plus tout seul, c'est le
  /// chauffeur qui décide (réessayer / abandonner).
  bool parked;

  OutboxItem({
    required this.id,
    required this.kind,
    required this.payload,
    required this.createdAt,
    this.attempts = 0,
    this.lastError,
    this.parked = false,
  });

  /// Libellé lisible pour la feuille « actions en attente ».
  String get libelle => switch (kind) {
    OutboxKind.presence =>
      '${payload['nom'] ?? 'Élève'} — ${payload['present'] == true ? 'montée' : 'dépose'}',
    OutboxKind.trajetDemarrer =>
      'Démarrer le trajet (${(payload['sens'] ?? '').toString().toLowerCase()})',
    OutboxKind.trajetTerminer => 'Terminer le trajet',
    OutboxKind.incident => 'Incident ${payload['type'] ?? ''}',
    OutboxKind.message => 'Message à l\'administration',
    OutboxKind.diffusion => 'Diffusion aux parents',
  };

  Map<String, dynamic> toJson() => {
    'id': id,
    'kind': kind.name,
    'payload': payload,
    'createdAt': createdAt.toIso8601String(),
    'attempts': attempts,
    'lastError': lastError,
    'parked': parked,
  };

  static OutboxItem? fromJson(Map<String, dynamic> j) {
    final kind = OutboxKind.values
        .where((k) => k.name == j['kind'])
        .firstOrNull;
    if (kind == null) return null; // item d'une version antérieure → ignoré
    return OutboxItem(
      id: (j['id'] ?? '') as String,
      kind: kind,
      payload: Map<String, dynamic>.from((j['payload'] ?? {}) as Map),
      createdAt:
          DateTime.tryParse((j['createdAt'] ?? '') as String) ?? DateTime.now(),
      attempts: (j['attempts'] as num?)?.toInt() ?? 0,
      lastError: j['lastError'] as String?,
      parked: (j['parked'] ?? false) as bool,
    );
  }
}

// ── Événements émis quand une écriture différée aboutit ──────────────────────

sealed class OutboxEvent {
  const OutboxEvent();
}

/// Le trajet a été créé (ou retrouvé par réconciliation) côté serveur.
class TrajetDemarreSync extends OutboxEvent {
  final Trajet trajet;
  const TrajetDemarreSync(this.trajet);
}

class TrajetTermineSync extends OutboxEvent {
  const TrajetTermineSync();
}

class PresenceSync extends OutboxEvent {
  final int eleveId;
  final bool present;
  const PresenceSync(this.eleveId, this.present);
}

/// Un item a définitivement échoué (plafond atteint) — il est « parké ».
class ItemParked extends OutboxEvent {
  final OutboxItem item;
  const ItemParked(this.item);
}

// ── Persistance ──────────────────────────────────────────────────────────────

/// Abstraction du stockage — permet un store mémoire dans les tests.
abstract class OutboxStore {
  Future<List<Map<String, dynamic>>> load();
  Future<void> save(List<Map<String, dynamic>> items);
}

/// Stockage réel : une simple liste JSON dans `shared_preferences`.
///
/// Choisi plutôt que sqflite (indisponible sur la cible Chrome) ou hive
/// (codegen) : quelques Ko de JSON, et surtout aucune dépendance à
/// `path_provider` — donc aucun contact avec le piège `jni`/AGP 9.
class PrefsOutboxStore implements OutboxStore {
  static const _key = 'outbox_chauffeur_v1';

  @override
  Future<List<Map<String, dynamic>>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null || raw.isEmpty) return const [];
    try {
      final list = jsonDecode(raw) as List;
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    } catch (_) {
      // Contenu corrompu : on repart propre plutôt que de bloquer l'app.
      await prefs.remove(_key);
      return const [];
    }
  }

  @override
  Future<void> save(List<Map<String, dynamic>> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(items));
  }
}

/// Store en mémoire (tests).
class MemoryOutboxStore implements OutboxStore {
  List<Map<String, dynamic>> _data = const [];

  @override
  Future<List<Map<String, dynamic>>> load() async => _data;

  @override
  Future<void> save(List<Map<String, dynamic>> items) async {
    // Copie profonde via JSON : reproduit la sérialisation réelle, donc un test
    // qui passe ici passe aussi avec le vrai store.
    _data = (jsonDecode(jsonEncode(items)) as List)
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
  }
}

// ── La file ──────────────────────────────────────────────────────────────────

enum _Outcome { done, retry, park }

/// File d'écritures différées, **FIFO strict et single-flight**.
///
/// Pourquoi FIFO strict : l'ordre est porteur de sens. « Démarrer le trajet »
/// doit atteindre le serveur avant les pointages de présence qui le suivent ;
/// vidanger en parallèle produirait des pointages sur un trajet inexistant.
///
/// Ce que la file ne fait PAS : rejouer des positions GPS. `PositionRequest`
/// n'a pas de champ horodatage (MS3 date côté serveur), donc réémettre un point
/// vieux de trois minutes écrirait une **fausse position courante**. En temps
/// réel, un point perdu doit rester perdu.
class Outbox extends ChangeNotifier {
  Outbox(this._api, {OutboxStore? store})
    : _store = store ?? PrefsOutboxStore();

  final ApiClient _api;
  final OutboxStore _store;

  final List<OutboxItem> _items = [];
  final _events = StreamController<OutboxEvent>.broadcast();

  bool _draining = false;
  int _seq = 0;

  /// Événements de synchronisation (à écouter pour recaler l'UI).
  Stream<OutboxEvent> get events => _events.stream;

  /// Items en attente d'envoi (hors items parkés).
  List<OutboxItem> get pending =>
      _items.where((i) => !i.parked).toList(growable: false);

  /// Items ayant épuisé leurs essais — décision rendue au chauffeur.
  List<OutboxItem> get parked =>
      _items.where((i) => i.parked).toList(growable: false);

  int get pendingCount => pending.length;
  int get parkedCount => parked.length;
  bool get isEmpty => _items.isEmpty;

  Future<void> init() async {
    final raw = await _store.load();
    _items
      ..clear()
      ..addAll(raw.map(OutboxItem.fromJson).whereType<OutboxItem>());
    notifyListeners();
  }

  Future<void> _persist() =>
      _store.save(_items.map((i) => i.toJson()).toList());

  String _nextId() => '${DateTime.now().microsecondsSinceEpoch}-${_seq++}';

  /// Met une écriture en file.
  ///
  /// Cas particulier de la présence : la valeur envoyée est **absolue**
  /// (`?present=true|false`), donc deux pointages successifs du même élève sont
  /// redondants — on ne garde que le dernier (« collapse »). Sans ça, une
  /// hésitation du chauffeur (monté → pas monté → monté) enverrait trois appels
  /// dont seul le dernier compte.
  Future<OutboxItem> enqueue(
    OutboxKind kind,
    Map<String, dynamic> payload,
  ) async {
    if (kind == OutboxKind.presence) {
      final eleveId = payload['eleveId'];
      _items.removeWhere(
        (i) =>
            i.kind == OutboxKind.presence &&
            !i.parked &&
            i.payload['eleveId'] == eleveId,
      );
    }
    final item = OutboxItem(
      id: _nextId(),
      kind: kind,
      payload: payload,
      createdAt: DateTime.now(),
    );
    _items.add(item);
    await _persist();
    notifyListeners();
    return item;
  }

  /// Relance un item parké à la demande du chauffeur.
  Future<void> retryParked(String id) async {
    for (final i in _items) {
      if (i.id == id) {
        i.parked = false;
        i.attempts = 0;
        i.lastError = null;
      }
    }
    await _persist();
    notifyListeners();
    unawaited(drain());
  }

  Future<void> remove(String id) async {
    _items.removeWhere((i) => i.id == id);
    await _persist();
    notifyListeners();
  }

  Future<void> clear() async {
    _items.clear();
    await _persist();
    notifyListeners();
  }

  /// Vide la file dans l'ordre. Réentrance protégée : un seul drain à la fois.
  ///
  /// Un item qui échoue **bloque la file** — c'est voulu : laisser passer les
  /// suivants casserait l'ordre (des pointages avant le démarrage du trajet).
  Future<void> drain() async {
    if (_draining) return;
    _draining = true;
    try {
      while (true) {
        final item = pending.isEmpty ? null : pending.first;
        if (item == null) break;

        item.attempts++;
        final outcome = await _run(item);

        if (outcome == _Outcome.done) {
          _items.remove(item);
          await _persist();
          notifyListeners();
          continue;
        }
        if (outcome == _Outcome.park) {
          item.parked = true;
          await _persist();
          notifyListeners();
          _events.add(ItemParked(item));
          continue; // l'item parké sort de `pending`, on passe au suivant
        }
        // retry : on s'arrête là, la file repartira au prochain déclencheur.
        await _persist();
        notifyListeners();
        break;
      }
    } finally {
      _draining = false;
    }
  }

  Future<_Outcome> _run(OutboxItem item) async {
    try {
      switch (item.kind) {
        case OutboxKind.presence:
          await _api.setPresence(
            item.payload['eleveId'] as int,
            item.payload['present'] as bool,
          );
          _events.add(
            PresenceSync(
              item.payload['eleveId'] as int,
              item.payload['present'] as bool,
            ),
          );
          return _Outcome.done;

        case OutboxKind.trajetDemarrer:
          final t = await _api.demarrerTrajet(
            busId: item.payload['busId'] as int,
            sens: item.payload['sens'] as String,
            groupeId: item.payload['groupeId'] as int?,
            geometrie: _geometrie(item.payload['geometrie']),
            distancePlanM: (item.payload['distancePlanM'] as num?)?.toDouble(),
            dureePlanMin: (item.payload['dureePlanMin'] as num?)?.toDouble(),
          );
          _events.add(TrajetDemarreSync(t));
          return _Outcome.done;

        case OutboxKind.trajetTerminer:
          await _api.terminerTrajet(item.payload['trajetId'] as int);
          _events.add(const TrajetTermineSync());
          return _Outcome.done;

        case OutboxKind.incident:
          await _api.creerIncident(
            type: item.payload['type'] as String,
            busId: item.payload['busId'] as int,
            description: item.payload['description'] as String?,
            latitude: (item.payload['latitude'] as num?)?.toDouble(),
            longitude: (item.payload['longitude'] as num?)?.toDouble(),
          );
          return _Outcome.done;

        case OutboxKind.message:
          await _api.envoyerMessage(item.payload['contenu'] as String);
          return _Outcome.done;

        case OutboxKind.diffusion:
          await _api.diffuserAuxParents(
            item.payload['busId'] as int,
            item.payload['contenu'] as String,
          );
          return _Outcome.done;
      }
    } catch (e) {
      item.lastError = friendlyError(e);

      // Coupure réseau : on n'a rien consommé, on retentera à l'identique.
      if (isOffline(e)) return _Outcome.retry;

      // Le serveur a répondu et a refusé. Pour les deux opérations dont le
      // rejeu n'est pas neutre, on va lire l'état réel avant de conclure.
      final reconcile = await _reconcilier(item);
      if (reconcile != null) return reconcile;

      return item.attempts >= Env.outboxMaxAttempts
          ? _Outcome.park
          : _Outcome.retry;
    }
  }

  /// Réconciliation des opérations non idempotentes.
  ///
  /// `POST /api/trajets/demarrer` refuse un second démarrage tant qu'un trajet
  /// est `EN_COURS` (MS1 `TrajetService.demarrer`). Rejouer aveuglément
  /// produirait donc une erreur permanente alors que l'effet voulu est déjà
  /// obtenu. On interroge `mon-actif` et on adopte ce que le serveur dit.
  ///
  /// Renvoie null si l'item n'est pas concerné (→ traitement d'échec normal).
  Future<_Outcome?> _reconcilier(OutboxItem item) async {
    if (item.kind != OutboxKind.trajetDemarrer &&
        item.kind != OutboxKind.trajetTerminer) {
      return null;
    }
    try {
      final actif = await _api.getMonTrajetActif();

      if (item.kind == OutboxKind.trajetDemarrer) {
        if (actif != null && actif.busId == item.payload['busId']) {
          _events.add(TrajetDemarreSync(actif));
          return _Outcome.done;
        }
        return null;
      }

      // trajetTerminer : plus de trajet actif, ou un autre → celui visé est clos.
      if (actif == null || actif.id != item.payload['trajetId']) {
        _events.add(const TrajetTermineSync());
        return _Outcome.done;
      }
      return null;
    } catch (_) {
      // La lecture de contrôle a échoué : on ne conclut rien, on retentera.
      return _Outcome.retry;
    }
  }

  List<List<double>>? _geometrie(dynamic raw) {
    if (raw is! List) return null;
    final pts = raw
        .whereType<List>()
        .map((p) => p.map((c) => (c as num).toDouble()).toList())
        .where((p) => p.length >= 2)
        .toList();
    return pts.isEmpty ? null : pts;
  }

  @override
  void dispose() {
    _events.close();
    super.dispose();
  }
}
