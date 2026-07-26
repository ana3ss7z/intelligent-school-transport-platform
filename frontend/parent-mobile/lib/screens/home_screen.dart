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
  /// Trajet actif par busId (null = aucun trajet démarré).
  final Map<int, Trajet?> _trajets = {};

  /// ETA (minutes) par eleveId.
  final Map<int, double?> _etas = {};

  Timer? _trajetTimer;
  Timer? _etaTimer;
  Timer? _childrenTimer;
  bool _kicked = false;

  @override
  void initState() {
    super.initState();
    _trajetTimer = Timer.periodic(Env.pollTrajet, (_) => _loadTrajets());
    _etaTimer = Timer.periodic(Env.pollEta, (_) => _loadEtas());
    // Rafraîchit enfants/présence périodiquement.
    _childrenTimer = Timer.periodic(Env.pollEta, (_) {
      ref.invalidate(childrenProvider);
    });
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
      } catch (_) {/* garde la valeur précédente */}
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
    // Démarre le chargement dès que « mes enfants » sont disponibles.
    ref.listen(childrenProvider, (prev, next) {
      if (next.hasValue && next.value!.enfants.isNotEmpty && !_kicked) {
        _kicked = true;
        _loadTrajets().then((_) => _loadEtas());
      }
    });

    final async = ref.watch(childrenProvider);
    final user = ref.watch(authProvider);

    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => ErrorRetry(
        message: friendlyError(e),
        onRetry: () => ref.invalidate(childrenProvider),
      ),
      data: (data) {
        if (data.enfants.isEmpty) {
          return const EmptyState(
            icon: Icons.family_restroom,
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
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                'Bonjour ${user?.nom ?? ''}',
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  _StatTile(
                      label: 'Mes enfants',
                      value: '${data.enfants.length}',
                      icon: Icons.child_care,
                      color: AppColors.route),
                  const SizedBox(width: 10),
                  _StatTile(
                      label: 'À bord',
                      value: '$aBord',
                      icon: Icons.event_seat,
                      color: AppColors.ok),
                  const SizedBox(width: 10),
                  _StatTile(
                      label: 'Bus',
                      value: '${data.busIds.length}',
                      icon: Icons.directions_bus,
                      color: AppColors.warn),
                ],
              ),
              const SizedBox(height: 16),
              ...data.enfants.map((e) => _ChildCard(
                    eleve: e,
                    bus: e.busId != null ? data.busById[e.busId] : null,
                    trajet: e.busId != null ? _trajets[e.busId] : null,
                    eta: _etas[e.id],
                  )),
            ],
          ),
        );
      },
    );
  }
}

class _StatTile extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;
  const _StatTile({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
          child: Column(
            children: [
              Icon(icon, color: color, size: 22),
              const SizedBox(height: 6),
              Text(value,
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
              Text(label,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 11, color: AppColors.inkSoft)),
            ],
          ),
        ),
      ),
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

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    eleve.nomComplet,
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
                Chip2(
                  eleve.statutPresence ? 'à bord' : 'pas à bord',
                  color: eleve.statutPresence ? AppColors.ok : AppColors.inkSoft,
                  icon: eleve.statutPresence ? Icons.check_circle : Icons.circle_outlined,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                if (eleve.groupeId != null) ...[
                  Chip2('Groupe ${eleve.groupeId}', color: AppColors.inkSoft),
                  const SizedBox(width: 6),
                ],
                if (bus != null)
                  Chip2(
                    'Bus ${bus!.matricule}',
                    color: busStatusColor(bus!.statut),
                    icon: Icons.directions_bus,
                  )
                else
                  const Chip2('Aucun bus', color: AppColors.inkSoft),
              ],
            ),
            const SizedBox(height: 10),
            _countdown(),
          ],
        ),
      ),
    );
  }

  Widget _countdown() {
    if (trajet == null) {
      return const Text('Aucun trajet en cours.',
          style: TextStyle(fontSize: 12, color: AppColors.inkSoft));
    }
    final soir = trajet!.isSoir;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.route.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          const Icon(Icons.access_time, size: 16, color: AppColors.route),
          const SizedBox(width: 8),
          Expanded(
            child: eta != null
                ? Text.rich(
                    TextSpan(children: [
                      const TextSpan(text: 'Le bus arrive dans '),
                      TextSpan(
                        text: '~${eta!.round()} min',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                      TextSpan(
                        text: soir ? ' chez vous' : ' à l\'école',
                        style: const TextStyle(color: AppColors.inkSoft),
                      ),
                    ]),
                    style: const TextStyle(fontSize: 13),
                  )
                : Text(
                    'Trajet ${soir ? "du soir" : "du matin"} en cours — calcul de l\'arrivée…',
                    style: const TextStyle(fontSize: 13, color: AppColors.inkSoft),
                  ),
          ),
        ],
      ),
    );
  }
}
