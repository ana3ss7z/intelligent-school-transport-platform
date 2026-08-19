import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api.dart';
import '../models/models.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Prévisions d'arrivée pour MES enfants.
///
/// Le parent choisit le sens (matin = ramassage, soir = dépose) et l'heure de départ de l'école ;
/// MS5 renvoie le rang et le cumul depuis l'école le long de la tournée optimisée (uniquement
/// pour ses enfants), et MS12 convertit ce cumul en heure d'arrivée dans les conditions du jour.
class EtaScreen extends ConsumerStatefulWidget {
  const EtaScreen({super.key});

  @override
  ConsumerState<EtaScreen> createState() => _EtaScreenState();
}

class _Prevision {
  final EtapeEnfant etape;
  final double etaMin;
  final String arrivee;
  const _Prevision(this.etape, this.etaMin, this.arrivee);
}

class _EtaScreenState extends ConsumerState<EtaScreen> {
  String _sens = 'matin';
  TimeOfDay _heure = const TimeOfDay(hour: 7, minute: 30);
  bool _busy = false;
  String? _erreur;
  List<_Prevision>? _prevs;

  bool get _matin => _sens == 'matin';
  double get _heureDec => _heure.hour + _heure.minute / 60.0;

  void _setSens(String s) {
    setState(() {
      _sens = s;
      _heure = s == 'matin'
          ? const TimeOfDay(hour: 7, minute: 30)
          : const TimeOfDay(hour: 17, minute: 30);
      _prevs = null;
      _erreur = null;
    });
  }

  String _clock(double depart, double minutes) {
    final t = depart + minutes / 60.0;
    final h = t.floor() % 24;
    final m = ((t - t.floor()) * 60).round() % 60;
    return '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}';
  }

  Future<void> _choisirHeure() async {
    final choix = await showTimePicker(context: context, initialTime: _heure);
    if (choix != null && mounted) setState(() => _heure = choix);
  }

  Future<void> _calculer() async {
    setState(() {
      _busy = true;
      _erreur = null;
      _prevs = null;
    });
    try {
      final etapes = await Api.instance.getEtaMesEnfants(_sens);
      final depart = _heureDec;
      final out = <_Prevision>[];
      for (final e in etapes) {
        double eta;
        try {
          final r = await Api.instance.predictEta(
            // Le cumul est une durée OSRM libre ; MS12 y applique les conditions du jour.
            distanceRoutiereM: e.cumulDistanceM,
            dureeBaseS: e.cumulDureeS,
            heureDepart: depart,
            moment: _sens,
          );
          eta = r.etaMinutes;
        } catch (_) {
          eta =
              e.cumulDureeS /
              60.0; // repli : durée libre, sans correction contextuelle
        }
        out.add(_Prevision(e, eta, _clock(depart, eta)));
      }
      if (mounted) setState(() => _prevs = out);
    } catch (e) {
      if (mounted) setState(() => _erreur = friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        Text(
          _matin
              ? 'Heure estimée à laquelle le bus passe prendre vos enfants.'
              : 'Heure estimée à laquelle le bus dépose vos enfants.',
          style: const TextStyle(color: AppColors.inkSoft, fontSize: 13),
        ),
        const SizedBox(height: AppSpacing.lg),
        _Controles(
          sens: _sens,
          heure: _heure,
          busy: _busy,
          onSens: _setSens,
          onHeure: _choisirHeure,
          onCalculer: _calculer,
        ),
        const SizedBox(height: AppSpacing.lg),
        if (_busy) const SkeletonCards(count: 2),
        if (!_busy && _erreur != null)
          ErrorRetry(message: _erreur!, onRetry: _calculer),
        if (!_busy && _erreur == null && _prevs != null) ...[
          if (_prevs!.isEmpty)
            const EmptyState(
              icon: Icons.event_busy_outlined,
              text: 'Aucun de vos enfants n\'est planifié sur une tournée.',
            )
          else ...[
            SectionHeader(
              _matin ? 'Passage estimé chez vous' : 'Dépose estimée chez vous',
              trailing: Chip2(
                'Départ ${_heure.format(context)}',
                icon: Icons.schedule_rounded,
              ),
            ),
            for (final p in _prevs!)
              Padding(
                key: ValueKey(p.etape.eleveId),
                padding: const EdgeInsets.only(bottom: AppSpacing.md),
                child: _CarteEnfant(prevision: p, matin: _matin),
              ),
            const SizedBox(height: AppSpacing.xs),
            const Text(
              'Estimation indicative : elle dépend du trafic, de la météo et des arrêts précédents.',
              style: TextStyle(color: AppColors.inkSoft, fontSize: 11),
            ),
          ],
        ],
        if (!_busy && _erreur == null && _prevs == null)
          const EmptyState(
            icon: Icons.schedule_rounded,
            text:
                'Choisissez le sens et l\'heure de départ, puis calculez les arrivées estimées.',
          ),
      ],
    );
  }
}

class _Controles extends StatelessWidget {
  final String sens;
  final TimeOfDay heure;
  final bool busy;
  final ValueChanged<String> onSens;
  final VoidCallback onHeure;
  final VoidCallback onCalculer;

  const _Controles({
    required this.sens,
    required this.heure,
    required this.busy,
    required this.onSens,
    required this.onHeure,
    required this.onCalculer,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(
                  value: 'matin',
                  label: Text('Matin'),
                  icon: Icon(Icons.wb_sunny_outlined),
                ),
                ButtonSegment(
                  value: 'soir',
                  label: Text('Soir'),
                  icon: Icon(Icons.nightlight_outlined),
                ),
              ],
              selected: {sens},
              onSelectionChanged: busy ? null : (s) => onSens(s.first),
            ),
            const SizedBox(height: AppSpacing.md),
            Row(
              children: [
                Expanded(
                  child: Semantics(
                    button: true,
                    label:
                        'Heure de départ de l\'école, ${heure.format(context)}',
                    child: OutlinedButton.icon(
                      onPressed: busy ? null : onHeure,
                      icon: const Icon(Icons.schedule_rounded),
                      label: Text('Départ ${heure.format(context)}'),
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: busy ? null : onCalculer,
                    icon: busy
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.play_arrow_rounded),
                    label: Text(busy ? 'Calcul…' : 'Calculer'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _CarteEnfant extends StatelessWidget {
  final _Prevision prevision;
  final bool matin;
  const _CarteEnfant({required this.prevision, required this.matin});

  @override
  Widget build(BuildContext context) {
    final e = prevision.etape;
    final km = (e.cumulDistanceM / 1000).toStringAsFixed(1);
    return Semantics(
      label:
          '${e.prenom} ${e.nom}, ${matin ? "pris" : "déposé"} vers ${prevision.arrivee}, '
          '${e.rang}e arrêt sur ${e.nArrets}',
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const CircleAvatar(
                    radius: 18,
                    backgroundColor: AppColors.route,
                    child: Icon(
                      Icons.school_rounded,
                      size: 18,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${e.prenom} ${e.nom}',
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        Text(
                          '${e.rang}ᵉ arrêt sur ${e.nArrets}',
                          style: const TextStyle(
                            color: AppColors.inkSoft,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        prevision.arrivee,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                          color: AppColors.route,
                        ),
                      ),
                      Text(
                        '~${prevision.etaMin.round()} min',
                        style: const TextStyle(
                          color: AppColors.inkSoft,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.xs,
                children: [
                  Chip2(
                    'Bus ${e.busId ?? "—"}',
                    icon: Icons.directions_bus_rounded,
                  ),
                  Chip2(
                    '$km km depuis l\'école',
                    color: AppColors.warn,
                    icon: Icons.route_rounded,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
