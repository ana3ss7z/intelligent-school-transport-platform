import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api.dart';
import '../config/env.dart';
import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/common.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final Map<int, Trajet?> _trajets = {}; // par busId
  final Map<int, double?> _etas = {}; // par eleveId

  Timer? _trajetTimer;
  Timer? _etaTimer;
  Timer? _childrenTimer;
  bool _kicked = false;

  @override
  void initState() {
    super.initState();
    _trajetTimer = Timer.periodic(Env.pollTrajet, (_) => _loadTrajets());
    _etaTimer = Timer.periodic(Env.pollEta, (_) => _loadEtas());
    _childrenTimer = Timer.periodic(
      Env.pollEta,
      (_) => ref.invalidate(childrenProvider),
    );
  }

  @override
  void dispose() {
    _trajetTimer?.cancel();
    _etaTimer?.cancel();
    _childrenTimer?.cancel();
    super.dispose();
  }

  ChildrenData? get _data => ref.read(childrenProvider).value;

  Future<void> _loadTrajets() async {
    final data = _data;
    if (data == null) return;
    for (final busId in data.busIds) {
      try {
        _trajets[busId] = await Api.instance.getTrajetActifBus(busId);
      } catch (_) {
        /* garde la valeur précédente */
      }
    }
    if (mounted) setState(() {});
  }

  Future<void> _loadEtas() async {
    final data = _data;
    if (data == null) return;
    final gps = ref.read(gpsSocketProvider);
    for (final e in data.enfants) {
      final busId = e.busId;
      final trajet = busId != null ? _trajets[busId] : null;
      if (busId == null || trajet == null) {
        _etas[e.id] = null;
        continue;
      }
      final bus = data.busById[busId];
      final live = gps.positions[busId];
      final lat = live?.latitude ?? bus?.latitude;
      final lng = live?.longitude ?? bus?.longitude;
      if (lat == null || lng == null) {
        _etas[e.id] = null;
        continue;
      }
      final soir = trajet.isSoir;
      final destLat = soir ? e.latitude : Env.ecoleLat;
      final destLng = soir ? e.longitude : Env.ecoleLng;
      if (destLat == null || destLng == null) {
        _etas[e.id] = null;
        continue;
      }
      try {
        final r = await Api.instance.predictEta(
          busLat: lat,
          busLng: lng,
          destLat: destLat,
          destLng: destLng,
          moment: soir ? 'soir' : 'matin',
        );
        _etas[e.id] = r.etaMinutes;
      } catch (_) {
        _etas[e.id] = null;
      }
    }
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(childrenProvider, (prev, next) {
      if (next.hasValue && next.value!.enfants.isNotEmpty && !_kicked) {
        _kicked = true;
        _loadTrajets().then((_) => _loadEtas());
      }
    });

    final async = ref.watch(childrenProvider);
    final user = ref.watch(authProvider);

    return async.when(
      loading: () => const SkeletonCards(count: 3),
      error: (e, _) => ErrorRetry(
        message: friendlyError(e),
        onRetry: () => ref.invalidate(childrenProvider),
      ),
      data: (data) {
        if (data.enfants.isEmpty) {
          return const EmptyState(
            icon: Icons.family_restroom_rounded,
            text: 'Aucun enfant associé à votre compte.',
          );
        }
        final aBord = data.enfants.where((e) => e.statutPresence).length;
        return RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(childrenProvider);
            await _loadTrajets();
            await _loadEtas();
          },
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            children: [
              Text(
                'Bonjour 👋',
                style: TextStyle(fontSize: 14, color: context.softColor),
              ),
              Text(
                user?.nom ?? '',
                style: const TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.4,
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              Row(
                children: [
                  StatTile(
                    label: 'Mes enfants',
                    value: '${data.enfants.length}',
                    icon: Icons.child_care_rounded,
                    color: AppColors.brand,
                  ),
                  const SizedBox(width: AppSpacing.md),
                  StatTile(
                    label: 'À bord',
                    value: '$aBord',
                    icon: Icons.event_seat_rounded,
                    color: AppColors.ok,
                  ),
                  const SizedBox(width: AppSpacing.md),
                  StatTile(
                    label: 'Bus',
                    value: '${data.busIds.length}',
                    icon: Icons.directions_bus_rounded,
                    color: AppColors.warn,
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xl),
              const SectionHeader('Mes enfants'),
              ...data.enfants.map(
                (e) => Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.md),
                  child: _ChildCard(
                    eleve: e,
                    bus: e.busId != null ? data.busById[e.busId] : null,
                    trajet: e.busId != null ? _trajets[e.busId] : null,
                    eta: _etas[e.id],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _ChildCard extends StatelessWidget {
  final Eleve eleve;
  final Bus? bus;
  final Trajet? trajet;
  final double? eta;
  const _ChildCard({
    required this.eleve,
    required this.bus,
    required this.trajet,
    required this.eta,
  });

  /// Résumé vocalisé d'un bloc (lecteurs d'écran) au lieu de fragments épars.
  String _semanticSummary() {
    final buf = StringBuffer(eleve.nomComplet);
    buf.write(present ? ', à bord du bus' : ', pas encore à bord');
    if (bus != null) buf.write(', bus ${bus!.matricule}');
    if (trajet == null) {
      buf.write('. Aucun trajet en cours.');
    } else if (eta != null) {
      buf.write(
        '. Le bus arrive dans environ ${eta!.round()} minutes '
        '${trajet!.isSoir ? "chez vous" : "à l'école"}.',
      );
    } else {
      buf.write(
        '. Trajet ${trajet!.isSoir ? "du soir" : "du matin"} en cours, '
        'calcul de l\'arrivée en cours.',
      );
    }
    return buf.toString();
  }

  bool get present => eleve.statutPresence;

  @override
  Widget build(BuildContext context) {
    final present = this.present;
    return Semantics(
      label: _semanticSummary(),
      excludeSemantics: true,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 22,
                    backgroundColor: AppColors.brand.withValues(alpha: 0.13),
                    child: Text(
                      eleve.prenom.isNotEmpty
                          ? eleve.prenom[0].toUpperCase()
                          : '?',
                      style: const TextStyle(
                        color: AppColors.brand,
                        fontWeight: FontWeight.w800,
                        fontSize: 18,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          eleve.nomComplet,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: [
                            if (eleve.groupeId != null)
                              Chip2(
                                'Groupe ${eleve.groupeId}',
                                color: context.softColor,
                              ),
                            if (bus != null)
                              Chip2(
                                'Bus ${bus!.matricule}',
                                color: busStatusColor(bus!.statut),
                                icon: Icons.directions_bus_rounded,
                              )
                            else
                              Chip2('Aucun bus', color: context.softColor),
                          ],
                        ),
                      ],
                    ),
                  ),
                  Chip2(
                    present ? 'à bord' : 'à quai',
                    color: present ? AppColors.ok : context.softColor,
                    icon: present
                        ? Icons.check_circle_rounded
                        : Icons.circle_outlined,
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              AnimatedSwitcher(
                duration: AppDurations.medium,
                transitionBuilder: (child, anim) =>
                    FadeTransition(opacity: anim, child: child),
                child: _countdown(context),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _countdown(BuildContext context) {
    if (trajet == null) {
      return Row(
        key: const ValueKey('none'),
        children: [
          Icon(Icons.bedtime_outlined, size: 15, color: context.softColor),
          const SizedBox(width: 6),
          Text(
            'Aucun trajet en cours',
            style: TextStyle(fontSize: 12.5, color: context.softColor),
          ),
        ],
      );
    }
    final soir = trajet!.isSoir;
    final hasEta = eta != null;
    final color = hasEta ? AppColors.brand : AppColors.warn;
    return Container(
      key: ValueKey('trajet-${trajet!.id}-$hasEta'),
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Row(
        children: [
          Icon(
            hasEta
                ? Icons.directions_bus_filled_rounded
                : Icons.schedule_rounded,
            size: 18,
            color: color,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: hasEta
                ? Text.rich(
                    TextSpan(
                      children: [
                        const TextSpan(text: 'Le bus arrive dans '),
                        TextSpan(
                          text: '~${eta!.round()} min',
                          style: const TextStyle(fontWeight: FontWeight.w800),
                        ),
                        TextSpan(
                          text: soir ? ' chez vous' : ' à l\'école',
                          style: TextStyle(color: context.softColor),
                        ),
                      ],
                    ),
                    style: const TextStyle(fontSize: 13.5),
                  )
                : Text(
                    'Trajet ${soir ? "du soir" : "du matin"} en cours — calcul de l\'arrivée…',
                    style: TextStyle(fontSize: 13, color: context.softColor),
                  ),
          ),
        ],
      ),
    );
  }
}
