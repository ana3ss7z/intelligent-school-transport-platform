import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../config/env.dart';
import '../models/models.dart';
import '../services/geo.dart';
import '../services/gps_emitter.dart';
import '../services/gps_socket.dart';
import '../services/outbox.dart';
import '../services/route_eta.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/common.dart';
import 'incidents_screen.dart';

/// « Ma tournée » — l'écran de travail du chauffeur.
///
/// Il concentre les trois écritures du métier : démarrer/terminer un trajet,
/// pointer les montées et déposes, signaler un incident. Chacune est
/// **optimiste** (l'UI bouge avant le serveur) avec rollback si le serveur
/// refuse, et **mise en file** si le réseau manque.
class TourneeScreen extends ConsumerStatefulWidget {
  const TourneeScreen({super.key});

  @override
  ConsumerState<TourneeScreen> createState() => _TourneeScreenState();
}

class _TourneeScreenState extends ConsumerState<TourneeScreen> {
  /// Identifiant local d'un trajet démarré hors ligne, pas encore accepté par
  /// MS1. Négatif pour ne jamais être confondu avec un id serveur.
  static const _idTrajetLocal = -1;

  Bus? _bus;
  Trajet? _trajet;
  List<Eleve> _eleves = const [];
  TourneePlan? _plan;
  bool _planDepuisCache = false;

  String _sensChoix = 'matin';
  double? _eta;
  String? _etaMode;

  /// Abscisse déjà atteinte sur le circuit. Empêche l'ETA de repartir en
  /// arrière quand le bus revient près de l'école (la tournée est un cycle
  /// fermé : sans ce garde-fou, le reste bondit de 1,5 min à 39 min à
  /// l'arrivée). Remis à -1 à chaque changement de trajet ou de tournée.
  double _alongM = -1;

  bool _chargement = true;
  bool _chargementEleves = false;
  bool _trajetBusy = false;
  String? _erreur;

  /// Pointage en cours d'envoi — sa valeur optimiste ne doit pas être écrasée
  /// par le sondage de présence.
  int? _pointageEnVol;

  Timer? _timerPresence;
  Timer? _timerEta;
  StreamSubscription<OutboxEvent>? _outboxSub;
  GpsSocket? _gps;

  String get _sens => _trajet?.sensBas ?? _sensChoix;
  bool get _enCours => _trajet != null;
  bool get _trajetLocal => _trajet != null && _trajet!.id == _idTrajetLocal;

  @override
  void initState() {
    super.initState();
    _outboxSub = ref.read(outboxProvider).events.listen(_onOutboxEvent);
    _timerPresence = Timer.periodic(Env.pollPresence, (_) => _sonderPresence());
    _timerEta = Timer.periodic(Env.pollEta, (_) => _calculerEta());
    WidgetsBinding.instance.addPostFrameCallback((_) => _chargerTout());
  }

  @override
  void dispose() {
    _timerPresence?.cancel();
    _timerEta?.cancel();
    _outboxSub?.cancel();
    _gps?.removeListener(_onGps);
    super.dispose();
  }

  // ────────────────────────────────────────────────────── Chargement
  Future<void> _chargerTout() async {
    if (!mounted) return;
    setState(() {
      _chargement = true;
      _erreur = null;
    });
    final api = ref.read(apiProvider);
    try {
      final buses = await api.getBus();
      final user = ref.read(authProvider);
      Bus? mien;
      for (final b in buses) {
        if (b.chauffeurId == user?.userId) mien = b;
      }
      if (!mounted) return;
      setState(() {
        _bus = mien;
        _chargement = false;
      });
      if (mien == null) return;

      // Trajet en cours restauré (relance de l'app en pleine tournée).
      try {
        final t = await api.getMonTrajetActif();
        if (mounted) setState(() => _trajet = t);
      } catch (_) {
        // Hors ligne : on garde l'état local s'il y en a un.
      }

      await _chargerEleves();
      await _chargerTournee();
      await _calculerEta();
      _syncEmetteur();
    } catch (e) {
      if (mounted) {
        setState(() {
          _chargement = false;
          _erreur = friendlyError(e);
        });
      }
    }
  }

  Future<void> _chargerEleves() async {
    final bus = _bus;
    if (bus == null) return;
    setState(() => _chargementEleves = true);
    try {
      final liste = await ref.read(apiProvider).getElevesParBus(bus.id);
      if (mounted) setState(() => _eleves = liste);
    } catch (_) {
      // Liste conservée telle quelle : mieux vaut une liste périmée que vide.
    } finally {
      if (mounted) setState(() => _chargementEleves = false);
    }
  }

  /// Tournée du groupe : réseau d'abord, cache local en repli.
  ///
  /// Quand un trajet est en cours, on privilégie la polyligne **figée** par MS1
  /// au démarrage : c'est celle que MS11 surveille et celle que l'app parent
  /// utilise pour son compte à rebours. Recalculer une tournée fraîche donnerait
  /// un ETA légèrement différent de celui vu par les familles.
  Future<void> _chargerTournee() async {
    final bus = _bus;
    final groupeId = _groupeId;
    if (bus == null) return;
    final api = ref.read(apiProvider);
    final cache = ref.read(tourneeCacheProvider);

    if (_enCours && !_trajetLocal) {
      try {
        final figee = await api.getTrajetRoute(bus.id);
        if (figee != null && figee.hasGeometrie && mounted) {
          setState(() {
            _plan = TourneePlan(
              sens: _sens,
              geometrie: figee.geometrie,
              distanceM: figee.distancePlanM,
              dureeMin: figee.dureePlanMin,
              ordre: _plan?.ordre ?? const [],
              etapes: _plan?.etapes ?? const [],
            );
            _planDepuisCache = false;
            _alongM = -1;
          });
          return;
        }
      } catch (_) {
        // On retombe sur la planification / le cache ci-dessous.
      }
    }

    if (groupeId == null) return;
    try {
      final plan = await api.getTournee(groupeId, _sens);
      if (!mounted) return;
      setState(() {
        _plan = plan;
        _planDepuisCache = false;
        _alongM = -1;
      });
      await cache.save(groupeId, _sens, plan);
    } catch (_) {
      final enCache = await cache.load(groupeId, _sens);
      if (enCache != null && mounted) {
        setState(() {
          _plan = enCache;
          _planDepuisCache = true;
          _alongM = -1;
        });
      }
    }
  }

  int? get _groupeId {
    for (final e in _eleves) {
      if (e.groupeId != null) return e.groupeId;
    }
    return _trajet?.groupeId;
  }

  /// Élèves dont la valeur locale fait foi : pointage en vol + pointages encore
  /// en file. Sans ça, le sondage réécrirait par-dessus une action hors ligne et
  /// le chauffeur verrait son pointage « revenir en arrière ».
  Set<int> get _nonSynchronises => {
    ?_pointageEnVol,
    for (final i in ref.read(outboxProvider).pending)
      if (i.kind == OutboxKind.presence) i.payload['eleveId'] as int,
  };

  Future<void> _sonderPresence() async {
    final bus = _bus;
    if (bus == null || !mounted) return;
    try {
      final frais = await ref.read(apiProvider).getElevesParBus(bus.id);
      if (!mounted) return;
      final garder = _nonSynchronises;
      final locaux = {for (final e in _eleves) e.id: e};
      setState(() {
        _eleves = [
          for (final e in frais)
            if (garder.contains(e.id) && locaux[e.id] != null)
              locaux[e.id]!
            else
              e,
        ];
      });
    } catch (_) {
      // Réseau instable : on conserve la liste courante.
    }
  }

  // ─────────────────────────────────────────────────────────── GPS
  void _bindGps(GpsSocket gps) {
    if (identical(_gps, gps)) return;
    _gps?.removeListener(_onGps);
    _gps = gps..addListener(_onGps);
  }

  void _onGps() {
    if (mounted) setState(() {});
  }

  double? get _lat {
    final bus = _bus;
    if (bus == null) return null;
    return _gps?.positions[bus.id]?.latitude ?? bus.latitude;
  }

  double? get _lng {
    final bus = _bus;
    if (bus == null) return null;
    return _gps?.positions[bus.id]?.longitude ?? bus.longitude;
  }

  void _syncEmetteur() {
    ref
        .read(gpsEmitterProvider)
        .bind(
          busId: _bus?.id,
          trajetActif: _enCours,
          matricule: _bus?.matricule ?? '',
        );
  }

  // ─────────────────────────────────────────────────────────── ETA
  /// ETA de **fin de tournée**.
  ///
  /// La tournée boucle école → élèves → école : viser l'école en point-à-point
  /// donne un ETA qui *augmente* pendant le ramassage, puisque le bus s'en
  /// éloigne. On mesure donc ce qui reste à parcourir SUR le circuit — arrêts
  /// restants compris — via [etaInputsRestants] avec une cible nulle
  /// (= terminus ; viser les coordonnées de l'école projetterait sur le départ).
  Future<void> _calculerEta() async {
    if (!mounted) return;
    final lat = _lat, lng = _lng;
    if (lat == null || lng == null) return;
    final poly = _plan?.geometrie;
    try {
      final inputs = (poly != null && poly.length >= 2)
          ? etaInputsRestants(
              poly,
              lat,
              lng,
              distancePlanM: _plan?.distanceM,
              dureePlanMin: _plan?.dureeMin,
              // On ne redescend jamais en dessous de l'abscisse déjà atteinte.
              depuisAlongM: _alongM,
            )
          : null;
      // Mémorisé AVANT l'appel réseau : même si MS12 ne répond pas, la
      // progression mesurée reste acquise.
      if (inputs != null) _alongM = inputs.alongM;
      final res = await ref
          .read(apiProvider)
          .predictEta(
            // Repli point-à-point tant que la tournée n'est pas chargée.
            busLat: inputs == null ? lat : null,
            busLng: inputs == null ? lng : null,
            destLat: inputs == null ? Env.ecoleLat : null,
            destLng: inputs == null ? Env.ecoleLng : null,
            distanceRoutiereM: inputs?.distanceM,
            dureeBaseS: inputs?.dureeBaseS,
            moment: _sens,
          );
      if (mounted) {
        setState(() {
          _eta = res.etaMinutes;
          _etaMode = res.modeEta;
        });
      }
    } catch (_) {
      // ETA indisponible : le KPI reste sur sa dernière valeur connue.
    }
  }

  // ────────────────────────────────────────────────── Cycle du trajet
  Future<void> _demarrer() async {
    final bus = _bus;
    if (bus == null) return;
    final plan = _plan;

    // Garde-fou volontaire : MS1 persiste la géométrie et MS11 s'en sert comme
    // référence de déviation (UC-8). Démarrer sans elle désarmerait la
    // surveillance SANS AUCUNE ERREUR VISIBLE — on préfère refuser.
    if (plan == null || !plan.hasGeometrie) {
      _snack(
        'Tournée indisponible : impossible de démarrer sans l\'itinéraire '
        '(il est envoyé à la supervision). Reconnectez-vous au réseau.',
        erreur: true,
      );
      return;
    }

    setState(() => _trajetBusy = true);
    _alongM = -1; // nouveau trajet → la progression repart du début du circuit
    final sensEnvoye = _sensChoix.toUpperCase();
    final payload = {
      'busId': bus.id,
      'sens': sensEnvoye,
      'groupeId': _groupeId,
      'geometrie': plan.geometrie,
      'distancePlanM': plan.distanceM,
      'dureePlanMin': plan.dureeMin,
    };

    try {
      final t = await ref
          .read(apiProvider)
          .demarrerTrajet(
            busId: bus.id,
            sens: sensEnvoye,
            groupeId: _groupeId,
            geometrie: plan.geometrie,
            distancePlanM: plan.distanceM,
            dureePlanMin: plan.dureeMin,
          );
      if (!mounted) return;
      setState(() => _trajet = t);
      _snack('Trajet $_sensChoix démarré — l\'administration est prévenue');
    } catch (e) {
      if (!mounted) return;
      if (isOffline(e)) {
        await ref
            .read(outboxProvider)
            .enqueue(OutboxKind.trajetDemarrer, payload);
        setState(
          () => _trajet = Trajet(
            id: _idTrajetLocal,
            busId: bus.id,
            matricule: bus.matricule,
            sens: sensEnvoye,
            heureDebut: DateTime.now().toIso8601String(),
            groupeId: _groupeId,
          ),
        );
        _snack('Hors ligne — le démarrage partira au retour du réseau');
      } else {
        _snack(friendlyError(e), erreur: true);
      }
    } finally {
      if (mounted) setState(() => _trajetBusy = false);
      _syncEmetteur();
      unawaited(_calculerEta());
    }
  }

  Future<void> _terminer() async {
    final t = _trajet;
    if (t == null) return;

    // Trajet encore en file : il n'existe pas côté serveur. Le « terminer »
    // reviendrait à envoyer un démarrage puis une clôture pour rien — on annule
    // le démarrage en attente.
    if (_trajetLocal) {
      final outbox = ref.read(outboxProvider);
      for (final i in outbox.pending) {
        if (i.kind == OutboxKind.trajetDemarrer) await outbox.remove(i.id);
      }
      setState(() => _trajet = null);
      _syncEmetteur();
      _snack('Démarrage en attente annulé — aucun trajet n\'avait été créé.');
      return;
    }

    setState(() => _trajetBusy = true);
    _alongM = -1;
    try {
      await ref.read(apiProvider).terminerTrajet(t.id);
      if (!mounted) return;
      setState(() => _trajet = null);
      _snack('Trajet terminé');
    } catch (e) {
      if (!mounted) return;
      if (isOffline(e)) {
        await ref.read(outboxProvider).enqueue(OutboxKind.trajetTerminer, {
          'trajetId': t.id,
        });
        setState(() => _trajet = null);
        _snack('Hors ligne — la clôture partira au retour du réseau');
      } else {
        _snack(friendlyError(e), erreur: true);
      }
    } finally {
      if (mounted) setState(() => _trajetBusy = false);
      _syncEmetteur();
    }
  }

  // ───────────────────────────────────────────────────────── Pointage
  Future<void> _pointer(Eleve e) async {
    if (!_enCours || _pointageEnVol != null) return;
    final suivant = !e.statutPresence;

    setState(() {
      _pointageEnVol = e.id;
      _eleves = [
        for (final x in _eleves)
          if (x.id == e.id) x.copyWith(statutPresence: suivant) else x,
      ];
    });

    try {
      await ref.read(apiProvider).setPresence(e.id, suivant);
      if (!mounted) return;
      final verbe = _sens == 'matin'
          ? (suivant ? 'monté' : 'retiré')
          : (suivant ? 'remis à bord' : 'déposé');
      _snack('${e.nomComplet} — $verbe');
    } catch (err) {
      if (!mounted) return;
      if (isOffline(err)) {
        await ref.read(outboxProvider).enqueue(OutboxKind.presence, {
          'eleveId': e.id,
          'present': suivant,
          'nom': e.nomComplet,
        });
        _snack('Hors ligne — pointage enregistré, il partira tout seul');
      } else {
        // Le serveur a refusé : on remet la valeur d'avant plutôt que de
        // laisser une coche qui ne correspond à rien côté base.
        setState(() {
          _eleves = [
            for (final x in _eleves)
              if (x.id == e.id) x.copyWith(statutPresence: !suivant) else x,
          ];
        });
        _snack(friendlyError(err), erreur: true);
      }
    } finally {
      if (mounted) setState(() => _pointageEnVol = null);
      // Une montée change l'ETA : recalcul immédiat plutôt qu'à la prochaine
      // échéance de 30 s.
      unawaited(_calculerEta());
    }
  }

  void _onOutboxEvent(OutboxEvent ev) {
    if (!mounted) return;
    switch (ev) {
      case TrajetDemarreSync(:final trajet):
        setState(() => _trajet = trajet);
        _syncEmetteur();
        unawaited(_chargerTournee());
      case TrajetTermineSync():
        setState(() => _trajet = null);
        // La progression n'a de sens que dans un trajet : le cas est rattrapé
        // par `_demarrer`, mais laisser une abscisse d'un trajet clos rendrait
        // l'état incohérent entre les deux chemins.
        _alongM = -1;
        _syncEmetteur();
      case PresenceSync():
        unawaited(_sonderPresence());
      case ItemParked(:final item):
        _snack('Action non envoyée : ${item.libelle}', erreur: true);
    }
  }

  void _snack(String message, {bool erreur = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: erreur ? AppColors.danger : null,
        ),
      );
  }

  // ─────────────────────────────────────────────────────────── Rendu
  @override
  Widget build(BuildContext context) {
    _bindGps(ref.watch(gpsSocketProvider));

    if (_chargement) return const SkeletonCards(count: 3);
    if (_erreur != null) {
      return ErrorRetry(message: _erreur!, onRetry: _chargerTout);
    }
    final bus = _bus;
    if (bus == null) {
      return const EmptyState(
        icon: Icons.no_transfer_outlined,
        text:
            'Aucun bus ne vous est affecté.\n'
            'Contactez l\'administration.',
      );
    }

    final total = _eleves.length;
    final faits = _enCours
        ? _eleves
              .where(
                (e) => _sens == 'matin' ? e.statutPresence : !e.statutPresence,
              )
              .length
        : 0;
    final prochain = _prochainArret();

    return RefreshIndicator(
      onRefresh: _chargerTout,
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        children: [
          _BandeauTrajet(
            enCours: _enCours,
            enAttenteReseau: _trajetLocal,
            sens: _sens,
            sensChoix: _sensChoix,
            onSensChange: (s) {
              setState(() => _sensChoix = s);
              unawaited(_chargerTournee());
            },
            heureDebut: _trajet?.heureDebut,
            busy: _trajetBusy,
            peutDemarrer: _plan?.hasGeometrie ?? false,
            onDemarrer: _demarrer,
            onTerminer: _terminer,
            faits: faits,
            total: total,
          ),
          const SizedBox(height: AppSpacing.md),
          if (_planDepuisCache) ...[
            _Avertissement(
              icone: Icons.cloud_off_rounded,
              texte:
                  'Itinéraire chargé depuis la mémoire de l\'appareil '
                  '(dernière version connue).',
            ),
            const SizedBox(height: AppSpacing.md),
          ],
          _Kpis(
            bus: bus,
            prochain: prochain,
            distanceProchain: _distanceProchain(prochain),
            faits: faits,
            total: total,
            sens: _sens,
            eta: _eta,
            etaSurCircuit: _plan?.hasGeometrie ?? false,
            etaMode: _etaMode,
          ),
          const SizedBox(height: AppSpacing.md),
          const _CarteEmissionGps(),
          const SizedBox(height: AppSpacing.md),
          _ActionsRapides(
            onSignaler: () => showIncidentDialog(
              context,
              ref,
              busId: bus.id,
              matricule: bus.matricule,
              latitude: _lat,
              longitude: _lng,
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          SectionHeader(
            'Tournée & pointage',
            trailing: Text(
              _enCours
                  ? '$faits/$total ${_sens == 'matin' ? 'montés' : 'déposés'}'
                  : 'démarrez pour pointer',
              style: TextStyle(fontSize: 12, color: context.softColor),
            ),
          ),
          if (_chargementEleves && _eleves.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: AppSpacing.lg),
              child: Skeleton(height: 48),
            )
          else if (_eleves.isEmpty)
            const EmptyState(
              icon: Icons.groups_outlined,
              text:
                  'Aucun élève affecté à ce bus.\n'
                  '(Le regroupement MS6 a-t-il été appliqué ?)',
            )
          else
            for (final e in _eleves)
              _LigneEleve(
                key: ValueKey(e.id),
                eleve: e,
                sens: _sens,
                actif: _enCours,
                enVol: _pointageEnVol == e.id,
                estProchain: prochain?.id == e.id,
                distance: prochain?.id == e.id
                    ? _distanceProchain(prochain)
                    : null,
                onTap: () => _pointer(e),
              ),
        ],
      ),
    );
  }

  /// Premier élève, dans l'ordre de passage, restant à traiter.
  Eleve? _prochainArret() {
    if (!_enCours) return null;
    for (final e in _eleves) {
      final reste = _sens == 'matin' ? !e.statutPresence : e.statutPresence;
      if (reste) return e;
    }
    return null;
  }

  double? _distanceProchain(Eleve? prochain) {
    final lat = _lat, lng = _lng;
    if (prochain == null ||
        lat == null ||
        lng == null ||
        prochain.latitude == null ||
        prochain.longitude == null) {
      return null;
    }
    return distanceHaversineM(
      lat,
      lng,
      prochain.latitude!,
      prochain.longitude!,
    );
  }
}

// ─────────────────────────────────────────────────────────── Sous-widgets

class _BandeauTrajet extends StatelessWidget {
  const _BandeauTrajet({
    required this.enCours,
    required this.enAttenteReseau,
    required this.sens,
    required this.sensChoix,
    required this.onSensChange,
    required this.heureDebut,
    required this.busy,
    required this.peutDemarrer,
    required this.onDemarrer,
    required this.onTerminer,
    required this.faits,
    required this.total,
  });

  final bool enCours;
  final bool enAttenteReseau;
  final String sens;
  final String sensChoix;
  final ValueChanged<String> onSensChange;
  final String? heureDebut;
  final bool busy;
  final bool peutDemarrer;
  final VoidCallback onDemarrer;
  final VoidCallback onTerminer;
  final int faits;
  final int total;

  @override
  Widget build(BuildContext context) {
    final progression = total == 0 ? 0.0 : faits / total;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: enCours
            ? Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Chip2(
                        enAttenteReseau
                            ? 'Trajet $sens (en attente d\'envoi)'
                            : 'Trajet $sens en cours',
                        color: enAttenteReseau ? AppColors.warn : AppColors.ok,
                        icon: enAttenteReseau
                            ? Icons.cloud_upload_outlined
                            : Icons.play_circle_outline,
                      ),
                      const Spacer(),
                      if (heureDebut != null)
                        Text(
                          'depuis ${_heure(heureDebut!)}',
                          style: TextStyle(
                            fontSize: 12,
                            color: context.softColor,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.md),
                  Semantics(
                    label:
                        '$faits sur $total ${sens == 'matin' ? 'montés' : 'déposés'}',
                    excludeSemantics: true,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(AppRadius.pill),
                      child: LinearProgressIndicator(
                        value: progression,
                        minHeight: 8,
                        backgroundColor: context.borderColor,
                        valueColor: const AlwaysStoppedAnimation(AppColors.ok),
                      ),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      onPressed: busy ? null : onTerminer,
                      icon: const Icon(Icons.flag_outlined, size: 18),
                      label: Text(busy ? '…' : 'Terminer le trajet'),
                    ),
                  ),
                ],
              )
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Aucun trajet en cours',
                    style: TextStyle(color: context.softColor, fontSize: 13),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(
                        value: 'matin',
                        label: Text('Matin'),
                        icon: Icon(Icons.wb_sunny_outlined, size: 16),
                      ),
                      ButtonSegment(
                        value: 'soir',
                        label: Text('Soir'),
                        icon: Icon(Icons.nights_stay_outlined, size: 16),
                      ),
                    ],
                    selected: {sensChoix},
                    onSelectionChanged: (s) => onSensChange(s.first),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      // Désactivé tant qu'on n'a pas d'itinéraire : voir
                      // le garde-fou dans `_demarrer`.
                      onPressed: (busy || !peutDemarrer) ? null : onDemarrer,
                      icon: const Icon(Icons.play_arrow_rounded, size: 20),
                      label: Text(busy ? '…' : 'Démarrer le trajet'),
                    ),
                  ),
                  if (!peutDemarrer) ...[
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      'En attente de l\'itinéraire de la tournée…',
                      style: TextStyle(fontSize: 12, color: context.softColor),
                    ),
                  ],
                ],
              ),
      ),
    );
  }

  static String _heure(String iso) {
    final dt = DateTime.tryParse(iso);
    if (dt == null) return '';
    return '${dt.hour.toString().padLeft(2, '0')}:'
        '${dt.minute.toString().padLeft(2, '0')}';
  }
}

class _Kpis extends StatelessWidget {
  const _Kpis({
    required this.bus,
    required this.prochain,
    required this.distanceProchain,
    required this.faits,
    required this.total,
    required this.sens,
    required this.eta,
    required this.etaSurCircuit,
    required this.etaMode,
  });

  final Bus bus;
  final Eleve? prochain;
  final double? distanceProchain;
  final int faits;
  final int total;
  final String sens;
  final double? eta;
  final bool etaSurCircuit;
  final String? etaMode;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          children: [
            StatTile(
              label: 'Mon bus',
              value: bus.matricule,
              icon: Icons.directions_bus_rounded,
              color: AppColors.route,
            ),
            const SizedBox(width: AppSpacing.md),
            StatTile(
              label: sens == 'matin' ? 'Montés' : 'Déposés',
              value: '$faits/$total',
              icon: Icons.how_to_reg_outlined,
              color: AppColors.ok,
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        Row(
          children: [
            StatTile(
              label: prochain == null
                  ? 'Prochain arrêt'
                  : (distanceProchain != null
                        ? 'à ${_fmtDist(distanceProchain!)}'
                        : (sens == 'matin' ? 'à monter' : 'à déposer')),
              value: prochain?.nomComplet ?? '—',
              icon: Icons.place_outlined,
              color: AppColors.route,
            ),
            const SizedBox(width: AppSpacing.md),
            StatTile(
              // « Fin de tournée » et non « arrivée à l'école » : le circuit
              // boucle, ce qui reste inclut tous les arrêts non desservis.
              label: etaSurCircuit
                  ? 'Fin de tournée'
                  : 'Fin de tournée (approx.)',
              value: eta == null ? '—' : '~${eta!.round()} min',
              icon: Icons.timer_outlined,
              color: AppColors.warn,
            ),
          ],
        ),
        if (etaMode == 'facteur_contexte')
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.sm),
            child: Text(
              'ETA ajusté au contexte (trajet plus long que ceux vus à '
              'l\'entraînement du modèle).',
              style: TextStyle(fontSize: 11, color: context.softColor),
            ),
          ),
      ],
    );
  }

  static String _fmtDist(double m) => m < 1000
      ? '~${(m / 10).round() * 10} m'
      : '~${(m / 1000).toStringAsFixed(1)} km';
}

/// Interrupteur d'émission GPS — le téléphone devient la source de position.
class _CarteEmissionGps extends ConsumerWidget {
  const _CarteEmissionGps();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final emitter = ref.watch(gpsEmitterProvider);
    return ListenableBuilder(
      listenable: emitter,
      builder: (context, _) {
        final etat = emitter.etat;
        final (couleur, texte) = switch (etat) {
          GpsEmitterState.emission => (
            AppColors.driver,
            '${emitter.envoyees} position(s) transmise(s)',
          ),
          GpsEmitterState.enAttente => (
            AppColors.inkSoft,
            'Démarrez un trajet pour transmettre votre position',
          ),
          GpsEmitterState.bloque => (
            AppColors.danger,
            emitter.erreur ?? 'Localisation indisponible',
          ),
          GpsEmitterState.off => (
            AppColors.inkSoft,
            'Position transmise par le simulateur',
          ),
        };
        return Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.lg,
              vertical: AppSpacing.sm,
            ),
            child: Column(
              children: [
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  value: emitter.enabled,
                  onChanged: (v) => emitter.setEnabled(v),
                  secondary: Icon(
                    etat == GpsEmitterState.emission
                        ? Icons.gps_fixed_rounded
                        : Icons.gps_off_rounded,
                    color: couleur,
                  ),
                  title: const Text('Transmettre ma position'),
                  subtitle: Text(
                    texte,
                    style: TextStyle(fontSize: 12, color: couleur),
                  ),
                ),
                if (etat == GpsEmitterState.bloque)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      onPressed: emitter.ouvrirReglages,
                      icon: const Icon(Icons.settings_outlined, size: 16),
                      label: const Text('Ouvrir les réglages'),
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _ActionsRapides extends StatelessWidget {
  const _ActionsRapides({required this.onSignaler});
  final VoidCallback onSignaler;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: onSignaler,
        style: OutlinedButton.styleFrom(foregroundColor: AppColors.danger),
        icon: const Icon(Icons.warning_amber_rounded, size: 18),
        label: const Text('Signaler un incident'),
      ),
    );
  }
}

class _Avertissement extends StatelessWidget {
  const _Avertissement({required this.icone, required this.texte});
  final IconData icone;
  final String texte;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.warn.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      child: Row(
        children: [
          Icon(icone, size: 18, color: AppColors.warn),
          const SizedBox(width: AppSpacing.sm),
          Expanded(child: Text(texte, style: const TextStyle(fontSize: 12.5))),
        ],
      ),
    );
  }
}

class _LigneEleve extends StatelessWidget {
  const _LigneEleve({
    super.key,
    required this.eleve,
    required this.sens,
    required this.actif,
    required this.enVol,
    required this.estProchain,
    required this.distance,
    required this.onTap,
  });

  final Eleve eleve;
  final String sens;
  final bool actif;
  final bool enVol;
  final bool estProchain;
  final double? distance;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final aBord = eleve.statutPresence;
    final etiquette = sens == 'matin'
        ? (aBord ? 'à bord' : 'à monter')
        : (aBord ? 'à déposer' : 'déposé');

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Semantics(
        button: actif,
        label:
            '${eleve.nomComplet}, arrêt ${eleve.ordrePassage ?? '?'}, $etiquette'
            '${estProchain ? ', prochain arrêt' : ''}',
        excludeSemantics: true,
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(AppRadius.md),
            onTap: (actif && !enVol) ? onTap : null,
            child: Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.md,
              ),
              decoration: BoxDecoration(
                color: estProchain
                    ? AppColors.route.withValues(alpha: 0.07)
                    : null,
                borderRadius: BorderRadius.circular(AppRadius.md),
                border: Border.all(
                  color: estProchain ? AppColors.route : context.borderColor,
                  width: estProchain ? 1.5 : 1,
                ),
              ),
              child: Opacity(
                opacity: actif ? 1 : 0.55,
                child: Row(
                  children: [
                    SizedBox(
                      width: 26,
                      child: Text(
                        '${eleve.ordrePassage ?? '—'}',
                        style: TextStyle(
                          fontFeatures: const [],
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: context.softColor,
                        ),
                      ),
                    ),
                    AnimatedContainer(
                      duration: AppDurations.fast,
                      width: 26,
                      height: 26,
                      decoration: BoxDecoration(
                        color: aBord ? AppColors.ok : context.borderColor,
                        shape: BoxShape.circle,
                      ),
                      child: enVol
                          ? const Padding(
                              padding: EdgeInsets.all(6),
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : Icon(
                              aBord
                                  ? Icons.check_rounded
                                  : Icons.circle_outlined,
                              size: 15,
                              color: aBord ? Colors.white : context.softColor,
                            ),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            eleve.nomComplet,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          if (estProchain)
                            Text(
                              distance != null
                                  ? 'prochain arrêt · ${_Kpis._fmtDist(distance!)}'
                                  : 'prochain arrêt',
                              style: const TextStyle(
                                fontSize: 11.5,
                                fontWeight: FontWeight.w700,
                                color: AppColors.route,
                              ),
                            ),
                        ],
                      ),
                    ),
                    Chip2(
                      etiquette,
                      color: aBord ? AppColors.ok : AppColors.inkSoft,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
