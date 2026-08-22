import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Prévisions : heure de passage estimée à chaque arrêt de ma tournée.
///
/// Méthode — et pourquoi elle diffère de la page web `/chauffeur/eta` :
/// la console web interroge MS12 **tronçon par tronçon** puis additionne. C'est
/// défendable (chaque tronçon tombe dans le domaine d'entraînement du modèle)
/// mais ce n'est pas ce que voient les familles : la page « Prévisions » parent
/// part du **cumul depuis l'école** fourni par MS5 (`etapes`) et le passe à MS12
/// en une fois, ce qui déclenche la garde anti-extrapolation (`facteur_contexte`).
/// Deux méthodes = deux heures affichées pour le même enfant. On s'aligne donc
/// sur celle du parent : mieux vaut un chiffre partagé qu'un chiffre isolé.
class EtaScreen extends ConsumerStatefulWidget {
  const EtaScreen({super.key});

  @override
  ConsumerState<EtaScreen> createState() => _EtaScreenState();
}

class _EtaScreenState extends ConsumerState<EtaScreen> {
  /// MS12 est appelé une fois par arrêt. Sur un bus de 50 élèves, tout lancer
  /// d'un coup dépasse le rate-limiter de la Gateway (20 req/s) et une partie
  /// des appels revient en 429. On plafonne donc la concurrence.
  static const _concurrence = 6;

  String _sens = 'matin';
  TimeOfDay _depart = const TimeOfDay(hour: 7, minute: 30);
  bool _calcul = false;
  String? _erreur;
  List<_Passage>? _passages;
  double? _totalMin;

  Future<void> _calculer() async {
    final bus = await ref.read(myBusProvider.future);
    if (bus == null) return;
    setState(() {
      _calcul = true;
      _erreur = null;
      _passages = null;
    });

    final api = ref.read(apiProvider);
    try {
      final eleves = await api.getElevesParBus(bus.id);
      final groupeId = eleves
          .map((e) => e.groupeId)
          .whereType<int>()
          .firstOrNull;
      if (groupeId == null) {
        throw ApiException(
          'Ce bus n\'a pas de groupe : le regroupement n\'a pas été appliqué.',
        );
      }

      final plan = await api.getTournee(groupeId, _sens);
      if (plan.etapes.isEmpty) {
        throw ApiException('Aucun arrêt à planifier sur cette tournée.');
      }
      final parId = {for (final e in eleves) e.id: e};
      final depart = _depart.hour + _depart.minute / 60;

      final resultats = List<double?>.filled(plan.etapes.length, null);
      for (var debut = 0; debut < plan.etapes.length; debut += _concurrence) {
        final lot = <Future<void>>[];
        for (
          var i = debut;
          i < debut + _concurrence && i < plan.etapes.length;
          i++
        ) {
          final etape = plan.etapes[i];
          final index = i;
          lot.add(() async {
            try {
              final r = await api.predictEta(
                distanceRoutiereM: etape.cumulDistanceM,
                dureeBaseS: etape.cumulDureeS,
                heureDepart: depart,
                moment: _sens,
              );
              resultats[index] = r.etaMinutes;
            } catch (_) {
              // Repli sur la durée OSRM brute plutôt qu'un trou dans la liste :
              // le chauffeur garde une estimation, signalée comme telle.
              resultats[index] = null;
            }
          }());
        }
        await Future.wait(lot);
      }

      final passages = <_Passage>[];
      for (var i = 0; i < plan.etapes.length; i++) {
        final etape = plan.etapes[i];
        final eleve = parId[etape.eleveId];
        final minutes = resultats[i] ?? etape.cumulDureeS / 60;
        passages.add(
          _Passage(
            rang: etape.rang,
            nom: eleve?.nomComplet ?? 'Élève #${etape.eleveId}',
            minutes: minutes,
            heure: _heure(depart, minutes),
            distanceKm: etape.cumulDistanceM / 1000,
            estime: resultats[i] == null,
          ),
        );
      }

      if (!mounted) return;
      setState(() {
        _passages = passages;
        _totalMin = plan.dureeMin;
        _calcul = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _erreur = friendlyError(e);
        _calcul = false;
      });
    }
  }

  static String _heure(double departDecimal, double plusMinutes) {
    final total = departDecimal * 60 + plusMinutes;
    final h = (total ~/ 60) % 24;
    final m = (total % 60).round() % 60;
    return '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Prévisions ETA')),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        children: [
          Card(
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
                        icon: Icon(Icons.wb_sunny_outlined, size: 16),
                      ),
                      ButtonSegment(
                        value: 'soir',
                        label: Text('Soir'),
                        icon: Icon(Icons.nights_stay_outlined, size: 16),
                      ),
                    ],
                    selected: {_sens},
                    onSelectionChanged: (s) => setState(() {
                      _sens = s.first;
                      _depart = _sens == 'matin'
                          ? const TimeOfDay(hour: 7, minute: 30)
                          : const TimeOfDay(hour: 17, minute: 30);
                      _passages = null;
                    }),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  OutlinedButton.icon(
                    onPressed: () async {
                      final choix = await showTimePicker(
                        context: context,
                        initialTime: _depart,
                      );
                      if (choix != null) setState(() => _depart = choix);
                    },
                    icon: const Icon(Icons.schedule_rounded, size: 18),
                    label: Text(
                      'Départ de l\'école : ${_depart.hour.toString().padLeft(2, '0')}:'
                      '${_depart.minute.toString().padLeft(2, '0')}',
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  FilledButton.icon(
                    onPressed: _calcul ? null : _calculer,
                    icon: _calcul
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.play_arrow_rounded, size: 18),
                    label: Text(_calcul ? 'Calcul…' : 'Calculer'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          if (_erreur != null)
            ErrorRetry(message: _erreur!, onRetry: _calculer)
          else if (_calcul)
            const SkeletonCards(count: 4)
          else if (_passages == null)
            const EmptyState(
              icon: Icons.schedule_rounded,
              text:
                  'Choisissez le sens et l\'heure de départ,\n'
                  'puis lancez le calcul.',
            )
          else ...[
            SectionHeader(
              'Arrivées estimées',
              trailing: _totalMin == null
                  ? null
                  : Chip2(
                      'tournée ~${_totalMin!.round()} min',
                      color: AppColors.route,
                      icon: Icons.timelapse_rounded,
                    ),
            ),
            for (final p in _passages!)
              _LignePassage(key: ValueKey(p.rang), passage: p),
          ],
        ],
      ),
    );
  }
}

class _Passage {
  const _Passage({
    required this.rang,
    required this.nom,
    required this.minutes,
    required this.heure,
    required this.distanceKm,
    required this.estime,
  });

  final int rang;
  final String nom;
  final double minutes;
  final String heure;
  final double distanceKm;

  /// true = MS12 n'a pas répondu, on affiche la durée OSRM brute.
  final bool estime;
}

class _LignePassage extends StatelessWidget {
  const _LignePassage({super.key, required this.passage});
  final _Passage passage;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Semantics(
        label:
            '${passage.nom}, arrêt ${passage.rang}, passage vers ${passage.heure}',
        excludeSemantics: true,
        child: Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.lg,
              vertical: AppSpacing.md,
            ),
            child: Row(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  alignment: Alignment.center,
                  decoration: const BoxDecoration(
                    color: AppColors.route,
                    shape: BoxShape.circle,
                  ),
                  child: Text(
                    '${passage.rang}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        passage.nom,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      Text(
                        '${passage.distanceKm.toStringAsFixed(1)} km depuis l\'école'
                        '${passage.estime ? ' · estimation OSRM' : ''}',
                        style: TextStyle(
                          fontSize: 11.5,
                          color: context.softColor,
                        ),
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      passage.heure,
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 15,
                        color: AppColors.route,
                      ),
                    ),
                    Text(
                      '~${passage.minutes.round()} min',
                      style: TextStyle(fontSize: 11, color: context.softColor),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
