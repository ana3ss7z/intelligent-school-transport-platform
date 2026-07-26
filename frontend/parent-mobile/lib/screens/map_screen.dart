import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../api/api.dart';
import '../config/env.dart';
import '../services/gps_socket.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/common.dart';

class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen> {
  final _controller = MapController();
  final Map<int, double> _etas = {}; // busId -> minutes (→ école)
  Timer? _etaTimer;

  @override
  void initState() {
    super.initState();
    _etaTimer = Timer.periodic(Env.pollEta, (_) => _loadEtas());
  }

  @override
  void dispose() {
    _etaTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadEtas() async {
    final data = ref.read(childrenProvider).value;
    if (data == null) return;
    final gps = ref.read(gpsSocketProvider);
    for (final b in data.mesBus) {
      final live = gps.positions[b.id];
      final lat = live?.latitude ?? b.latitude;
      final lng = live?.longitude ?? b.longitude;
      if (lat == null || lng == null) continue;
      try {
        final r = await Api.instance.predictEta(
          busLat: lat,
          busLng: lng,
          destLat: Env.ecoleLat,
          destLng: Env.ecoleLng,
          moment: 'matin',
        );
        _etas[b.id] = r.etaMinutes;
      } catch (_) {/* ignore */}
    }
    if (mounted) setState(() {});
  }

  /// Positions bus filtrées aux bus des enfants (+ repli dernière position connue).
  Map<int, LatLng> _busPositions(ChildrenData data, GpsSocket gps) {
    final out = <int, LatLng>{};
    final idSet = data.busIds.toSet();
    for (final entry in gps.positions.entries) {
      if (idSet.contains(entry.key)) {
        out[entry.key] = LatLng(entry.value.latitude, entry.value.longitude);
      }
    }
    for (final b in data.mesBus) {
      if (!out.containsKey(b.id) && b.latitude != null && b.longitude != null) {
        out[b.id] = LatLng(b.latitude!, b.longitude!);
      }
    }
    return out;
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(childrenProvider);
    final gps = ref.watch(gpsSocketProvider);

    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => ErrorRetry(
        message: friendlyError(e),
        onRetry: () => ref.invalidate(childrenProvider),
      ),
      data: (data) {
        if (data.busIds.isEmpty) {
          return const EmptyState(
            icon: Icons.directions_bus_outlined,
            text: 'Aucun bus assigné à vos enfants pour le moment.',
          );
        }
        // Redessine à chaque mise à jour GPS.
        return ListenableBuilder(
          listenable: gps,
          builder: (context, _) {
            final busPos = _busPositions(data, gps);
            final etaMax = _etas.values.isEmpty
                ? null
                : _etas.values.reduce((a, b) => a < b ? a : b);
            return Stack(
              children: [
                FlutterMap(
                  mapController: _controller,
                  options: const MapOptions(
                    initialCenter: LatLng(Env.ecoleLat, Env.ecoleLng),
                    initialZoom: 13,
                    minZoom: 9,
                    maxZoom: 18,
                  ),
                  children: [
                    TileLayer(
                      urlTemplate:
                          'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
                      subdomains: const ['a', 'b', 'c', 'd'],
                      userAgentPackageName: 'ma.transport.parent_app',
                    ),
                    // Trails des bus.
                    PolylineLayer(
                      polylines: [
                        for (final id in data.busIds)
                          if ((gps.trails[id]?.length ?? 0) > 1)
                            Polyline(
                              points: gps.trails[id]!,
                              strokeWidth: 3,
                              color: AppColors.route.withValues(alpha: 0.5),
                            ),
                      ],
                    ),
                    MarkerLayer(
                      markers: [
                        // École
                        const Marker(
                          point: LatLng(Env.ecoleLat, Env.ecoleLng),
                          width: 40,
                          height: 40,
                          child: _PinIcon(
                              icon: Icons.school, color: AppColors.danger),
                        ),
                        // Enfants (domicile)
                        for (final e in data.enfants)
                          if (e.latitude != null && e.longitude != null)
                            Marker(
                              point: LatLng(e.latitude!, e.longitude!),
                              width: 30,
                              height: 30,
                              child: const _PinIcon(
                                  icon: Icons.home, color: AppColors.ok, size: 16),
                            ),
                        // Bus
                        for (final entry in busPos.entries)
                          Marker(
                            point: entry.value,
                            width: 44,
                            height: 44,
                            child: _BusMarker(
                              id: entry.key,
                              matricule: data.busById[entry.key]?.matricule,
                              eta: _etas[entry.key],
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
                // Bandeau haut : statut GPS + ETA.
                Positioned(
                  top: 10,
                  left: 10,
                  right: 10,
                  child: Row(
                    children: [
                      _pill(
                        gps.connected ? 'GPS connecté' : 'hors ligne',
                        gps.connected ? AppColors.ok : AppColors.inkSoft,
                        gps.connected ? Icons.gps_fixed : Icons.gps_off,
                      ),
                      const SizedBox(width: 8),
                      if (etaMax != null)
                        _pill('ETA ~${etaMax.round()} min → école',
                            AppColors.route, Icons.access_time),
                    ],
                  ),
                ),
                // Recentrer
                Positioned(
                  bottom: 16,
                  right: 16,
                  child: FloatingActionButton.small(
                    heroTag: 'recenter',
                    backgroundColor: Colors.white,
                    foregroundColor: AppColors.route,
                    onPressed: () {
                      final first = busPos.values.isNotEmpty
                          ? busPos.values.first
                          : const LatLng(Env.ecoleLat, Env.ecoleLng);
                      _controller.move(first, 14);
                    },
                    child: const Icon(Icons.my_location),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Widget _pill(String text, Color color, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(999),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withValues(alpha: 0.1),
              blurRadius: 6,
              offset: const Offset(0, 2)),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 5),
          Text(text,
              style: TextStyle(
                  color: color, fontSize: 12, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

class _PinIcon extends StatelessWidget {
  final IconData icon;
  final Color color;
  final double size;
  const _PinIcon({required this.icon, required this.color, this.size = 22});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
        border: Border.all(color: color, width: 2),
      ),
      child: Icon(icon, color: color, size: size),
    );
  }
}

class _BusMarker extends StatelessWidget {
  final int id;
  final String? matricule;
  final double? eta;
  const _BusMarker({required this.id, this.matricule, this.eta});

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: 'Bus ${matricule ?? id}'
          '${eta != null ? ' · ~${eta!.round()} min → école' : ''}',
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.route,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.white, width: 2),
          boxShadow: [
            BoxShadow(
                color: Colors.black.withValues(alpha: 0.3),
                blurRadius: 4,
                offset: const Offset(0, 1)),
          ],
        ),
        child: const Icon(Icons.directions_bus, color: Colors.white, size: 22),
      ),
    );
  }
}
