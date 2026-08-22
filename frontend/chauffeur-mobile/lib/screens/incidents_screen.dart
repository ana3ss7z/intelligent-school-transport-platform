import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../config/env.dart';
import '../models/models.dart';
import '../services/outbox.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Incidents du bus du chauffeur + formulaire de signalement.
class IncidentsScreen extends ConsumerStatefulWidget {
  const IncidentsScreen({super.key});

  @override
  ConsumerState<IncidentsScreen> createState() => _IncidentsScreenState();
}

class _IncidentsScreenState extends ConsumerState<IncidentsScreen> {
  List<Incident> _incidents = const [];
  bool _chargement = true;
  String? _erreur;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _charger());
    _timer = Timer.periodic(Env.pollInbox, (_) => _charger(silencieux: true));
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _charger({bool silencieux = false}) async {
    final bus = await ref.read(myBusProvider.future);
    if (bus == null) {
      if (mounted) {
        setState(() {
          _chargement = false;
          _erreur = null;
        });
      }
      return;
    }
    try {
      final liste = await ref.read(apiProvider).getIncidentsParBus(bus.id);
      if (!mounted) return;
      setState(() {
        _incidents = liste;
        _chargement = false;
        _erreur = null;
      });
    } catch (e) {
      if (!mounted) return;
      // Un rafraîchissement silencieux qui échoue ne doit pas remplacer une
      // liste affichée par un écran d'erreur.
      if (!silencieux) {
        setState(() {
          _chargement = false;
          _erreur = friendlyError(e);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final busAsync = ref.watch(myBusProvider);

    return Scaffold(
      body: busAsync.when(
        loading: () => const SkeletonCards(count: 3),
        error: (e, _) =>
            ErrorRetry(message: friendlyError(e), onRetry: _charger),
        data: (bus) {
          if (bus == null) {
            return const EmptyState(
              icon: Icons.no_transfer_outlined,
              text: 'Aucun bus ne vous est affecté.',
            );
          }
          if (_chargement) return const SkeletonCards(count: 3);
          if (_erreur != null) {
            return ErrorRetry(message: _erreur!, onRetry: _charger);
          }
          if (_incidents.isEmpty) {
            return RefreshIndicator(
              onRefresh: _charger,
              child: ListView(
                children: const [
                  SizedBox(height: 80),
                  EmptyState(
                    icon: Icons.verified_outlined,
                    text: 'Aucun incident signalé sur ce bus.',
                  ),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: _charger,
            child: ListView.builder(
              padding: const EdgeInsets.all(AppSpacing.lg),
              itemCount: _incidents.length,
              itemBuilder: (context, i) => _CarteIncident(
                key: ValueKey(_incidents[i].id),
                incident: _incidents[i],
              ),
            ),
          );
        },
      ),
      floatingActionButton: busAsync.value == null
          ? null
          : FloatingActionButton.extended(
              onPressed: () async {
                final bus = busAsync.value!;
                final envoye = await showIncidentDialog(
                  context,
                  ref,
                  busId: bus.id,
                  matricule: bus.matricule,
                );
                if (envoye == true) unawaited(_charger());
              },
              icon: const Icon(Icons.add_alert_outlined),
              label: const Text('Signaler'),
            ),
    );
  }
}

class _CarteIncident extends StatelessWidget {
  const _CarteIncident({super.key, required this.incident});
  final Incident incident;

  @override
  Widget build(BuildContext context) {
    final (couleur, libelle) = _statut(incident.statut);
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      incident.type.replaceAll('_', ' '),
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                      ),
                    ),
                  ),
                  Chip2(libelle, color: couleur),
                ],
              ),
              if ((incident.description ?? '').isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(incident.description!),
              ],
              const SizedBox(height: AppSpacing.sm),
              Text(
                formatDateFr(incident.dateSignalement),
                style: TextStyle(fontSize: 12, color: context.softColor),
              ),
              if ((incident.notesResolution ?? '').isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(AppSpacing.md),
                  decoration: BoxDecoration(
                    color: AppColors.ok.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(AppRadius.sm),
                  ),
                  child: Text(
                    'Résolution : ${incident.notesResolution}',
                    style: const TextStyle(fontSize: 12.5),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  static (Color, String) _statut(String s) => switch (s.toUpperCase()) {
    'RESOLU' => (AppColors.ok, 'résolu'),
    'EN_TRAITEMENT' => (AppColors.warn, 'en traitement'),
    'CONFIRME' => (AppColors.warn, 'confirmé'),
    _ => (AppColors.danger, 'signalé'),
  };
}

/// Formulaire de signalement, partagé entre « Ma tournée » et « Mes incidents ».
///
/// Renvoie `true` si l'incident est parti (ou a été mis en file).
Future<bool?> showIncidentDialog(
  BuildContext context,
  WidgetRef ref, {
  required int busId,
  required String matricule,
  double? latitude,
  double? longitude,
}) {
  return showDialog<bool>(
    context: context,
    builder: (dialogContext) => _DialogueIncident(
      busId: busId,
      matricule: matricule,
      latitude: latitude,
      longitude: longitude,
      ref: ref,
    ),
  );
}

class _DialogueIncident extends StatefulWidget {
  const _DialogueIncident({
    required this.busId,
    required this.matricule,
    required this.latitude,
    required this.longitude,
    required this.ref,
  });

  final int busId;
  final String matricule;
  final double? latitude;
  final double? longitude;
  final WidgetRef ref;

  @override
  State<_DialogueIncident> createState() => _DialogueIncidentState();
}

class _DialogueIncidentState extends State<_DialogueIncident> {
  String _type = kTypesIncident.first;
  final _description = TextEditingController();
  bool _envoi = false;

  @override
  void dispose() {
    _description.dispose();
    super.dispose();
  }

  Future<void> _signaler() async {
    setState(() => _envoi = true);
    final texte = _description.text.trim();
    try {
      await widget.ref
          .read(apiProvider)
          .creerIncident(
            type: _type,
            busId: widget.busId,
            description: texte.isEmpty ? null : texte,
            latitude: widget.latitude,
            longitude: widget.longitude,
          );
      if (!mounted) return;
      Navigator.pop(context, true);
      _toast('Incident signalé — l\'administration est prévenue');
    } catch (e) {
      if (!mounted) return;
      if (isOffline(e)) {
        // Un incident est justement ce qu'on signale quand ça va mal, souvent
        // là où le réseau est mauvais : il doit survivre à la coupure.
        await widget.ref.read(outboxProvider).enqueue(OutboxKind.incident, {
          'type': _type,
          'busId': widget.busId,
          'description': texte.isEmpty ? null : texte,
          'latitude': widget.latitude,
          'longitude': widget.longitude,
        });
        if (!mounted) return;
        Navigator.pop(context, true);
        _toast('Hors ligne — l\'incident partira au retour du réseau');
      } else {
        setState(() => _envoi = false);
        _toast(friendlyError(e), erreur: true);
      }
    }
  }

  void _toast(String message, {bool erreur = false}) {
    final messenger = ScaffoldMessenger.maybeOf(widget.ref.context);
    messenger?.showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: erreur ? AppColors.danger : null,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final aPosition = widget.latitude != null && widget.longitude != null;
    return AlertDialog(
      title: Text('Signaler — bus ${widget.matricule}'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            DropdownButtonFormField<String>(
              initialValue: _type,
              decoration: const InputDecoration(labelText: 'Type'),
              items: [
                for (final t in kTypesIncident)
                  DropdownMenuItem(
                    value: t,
                    child: Text(t.replaceAll('_', ' ')),
                  ),
              ],
              onChanged: _envoi
                  ? null
                  : (v) => setState(() => _type = v ?? _type),
            ),
            const SizedBox(height: AppSpacing.md),
            TextField(
              controller: _description,
              maxLines: 3,
              enabled: !_envoi,
              decoration: const InputDecoration(
                labelText: 'Description',
                hintText: 'Décrivez brièvement la situation…',
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Row(
              children: [
                Icon(
                  aPosition
                      ? Icons.my_location_rounded
                      : Icons.location_disabled_rounded,
                  size: 14,
                  color: context.softColor,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    aPosition
                        ? 'Votre position actuelle sera jointe.'
                        : 'Position inconnue — l\'incident partira sans coordonnées.',
                    style: TextStyle(fontSize: 11.5, color: context.softColor),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _envoi ? null : () => Navigator.pop(context, false),
          child: const Text('Annuler'),
        ),
        FilledButton.icon(
          onPressed: _envoi ? null : _signaler,
          style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
          icon: _envoi
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Icon(Icons.send_rounded, size: 16),
          label: Text(_envoi ? 'Envoi…' : 'Signaler'),
        ),
      ],
    );
  }
}
