import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Historique des trajets terminés du chauffeur (`GET /api/trajets/mes-trajets`).
class HistoriqueScreen extends ConsumerStatefulWidget {
  const HistoriqueScreen({super.key});

  @override
  ConsumerState<HistoriqueScreen> createState() => _HistoriqueScreenState();
}

class _HistoriqueScreenState extends ConsumerState<HistoriqueScreen> {
  List<Trajet> _trajets = const [];
  bool _chargement = true;
  String? _erreur;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _charger());
  }

  Future<void> _charger() async {
    if (mounted) setState(() => _erreur = null);
    try {
      final liste = await ref.read(apiProvider).getMesTrajets();
      if (!mounted) return;
      setState(() {
        _trajets = liste;
        _chargement = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _chargement = false;
        _erreur = friendlyError(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mes trajets')),
      body: _chargement
          ? const SkeletonCards(count: 4)
          : _erreur != null
          ? ErrorRetry(message: _erreur!, onRetry: _charger)
          : _trajets.isEmpty
          ? const EmptyState(
              icon: Icons.history_rounded,
              text: 'Aucun trajet terminé pour l\'instant.',
            )
          : RefreshIndicator(
              onRefresh: _charger,
              child: ListView.builder(
                padding: const EdgeInsets.all(AppSpacing.lg),
                itemCount: _trajets.length,
                itemBuilder: (context, i) =>
                    _Ligne(key: ValueKey(_trajets[i].id), trajet: _trajets[i]),
              ),
            ),
    );
  }
}

class _Ligne extends StatelessWidget {
  const _Ligne({super.key, required this.trajet});
  final Trajet trajet;

  @override
  Widget build(BuildContext context) {
    final debut = DateTime.tryParse(trajet.heureDebut ?? '');
    final fin = DateTime.tryParse(trajet.heureFin ?? '');
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(9),
                decoration: BoxDecoration(
                  color: AppColors.route.withValues(alpha: 0.13),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  trajet.isSoir
                      ? Icons.nights_stay_outlined
                      : Icons.wb_sunny_outlined,
                  size: 18,
                  color: AppColors.route,
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      debut == null
                          ? (trajet.isSoir ? 'Soir' : 'Matin')
                          : '${trajet.isSoir ? 'Soir' : 'Matin'} · '
                                '${DateFormat('EEEE d MMM', 'fr_FR').format(debut)}',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      [
                        if (debut != null) DateFormat('HH:mm').format(debut),
                        if (fin != null) DateFormat('HH:mm').format(fin),
                      ].join(' → '),
                      style: TextStyle(
                        fontSize: 12.5,
                        color: context.softColor,
                      ),
                    ),
                  ],
                ),
              ),
              Chip2(
                _duree(debut, fin),
                color: AppColors.inkSoft,
                icon: Icons.timelapse_rounded,
              ),
            ],
          ),
        ),
      ),
    );
  }

  static String _duree(DateTime? debut, DateTime? fin) {
    if (debut == null || fin == null) return '—';
    final min = fin.difference(debut).inMinutes;
    if (min < 0) return '—';
    if (min < 60) return '$min min';
    return '${min ~/ 60} h ${(min % 60).toString().padLeft(2, '0')}';
  }
}
