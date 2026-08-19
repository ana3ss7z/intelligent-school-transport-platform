import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../api/api.dart';
import '../config/env.dart';
import '../models/models.dart';
import '../services/gps_socket.dart';
import '../services/route_eta.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/common.dart';

class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen>
    with SingleTickerProviderStateMixin {
  final _controller = MapController();
  late final AnimationController _anim = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  );

  GpsSocket? _gps; // instance écoutée
  final Map<int, LatLng> _from = {};
  final Map<int, LatLng> _to = {};
  final Map<int, double> _etas = {}; // busId -> minutes
  final Map<int, bool> _versDomicile = {}; // busId -> destination visée
  final Map<int, Trajet?> _trajets = {}; // busId -> trajet actif
  final Map<int, TrajetRoute?> _routes = {}; // busId -> tournée figée
  Timer? _etaTimer;
  Timer? _trajetTimer;

  @override
  void initState() {
    super.initState();
    _loadTrajets();
    _trajetTimer = Timer.periodic(Env.pollTrajet, (_) => _loadTrajets());
    _etaTimer = Timer.periodic(Env.pollEta, (_) => _loadEtas());
  }

  @override
  void dispose() {
    _etaTimer?.cancel();
    _trajetTimer?.cancel();
    _gps?.removeListener(_onGps);
    _anim.dispose();
    super.dispose();
  }

  /// Lie l'écoute au ChangeNotifier GPS (re-lie si l'instance change).
  void _bind(GpsSocket gps) {
    if (identical(gps, _gps)) return;
    _gps?.removeListener(_onGps);
    _gps = gps;
    gps.addListener(_onGps);
  }

  /// Nouvelle position GPS → prépare l'interpolation puis anime.
  void _onGps() {
    final data = ref.read(childrenProvider).value;
    final gps = _gps;
    if (data == null || gps == null) return;
    for (final id in data.busIds) {
      final p = gps.positions[id];
      if (p == null) continue;
      final target = LatLng(p.latitude, p.longitude);
      _from[id] = _to[id] ?? target; // point de départ = ancienne cible
      _to[id] = target;
    }
    if (mounted) {
      _anim.forward(from: 0);
      setState(() {}); // maj puce connecté
    }
  }

  Future<void> _loadTrajets() async {
    final data = ref.read(childrenProvider).value;
    if (data == null) return;
    for (final id in data.busIds) {
      try {
        final avant = _trajets[id]?.id;
        final t = await Api.instance.getTrajetActifBus(id);
        _trajets[id] = t;
        // Tournée rechargée seulement au changement de trajet (polyligne volumineuse).
        if (t == null) {
          _routes.remove(id);
        } else if (t.id != avant || _routes[id] == null) {
          _routes[id] = await Api.instance.getTrajetRoute(id);
        }
      } catch (_) {
        /* garde la valeur précédente */
      }
    }
    if (mounted) setState(() {});
  }

  Future<void> _loadEtas() async {
    final data = ref.read(childrenProvider).value;
    final gps = ref.read(gpsSocketProvider);
    if (data == null) return;
    for (final b in data.mesBus) {
      final live = gps.positions[b.id];
      final lat = live?.latitude ?? b.latitude;
      final lng = live?.longitude ?? b.longitude;
      if (lat == null || lng == null) continue;

      // Même règle que « Mon espace » : tant que l'enfant n'est pas monté, la
      // destination utile est SON domicile (le bus vient le chercher) ; une fois
      // à bord le matin, c'est l'école ; le soir, c'est le domicile. Et la distance
      // se mesure LE LONG de la tournée, sinon l'ETA remonte pendant le ramassage.
      final enfant = data.enfants.where((e) => e.busId == b.id).firstOrNull;
      final soir = _trajets[b.id]?.isSoir ?? false;
      final versDomicile = enfant != null && (soir || !enfant.statutPresence);
      final destLat = versDomicile ? enfant.latitude : Env.ecoleLat;
      final destLng = versDomicile ? enfant.longitude : Env.ecoleLng;
      if (destLat == null || destLng == null) continue;

      final route = _routes[b.id];
      final inputs = route != null && route.hasGeometrie
          ? etaInputsRestants(
              route.geometrie,
              lat,
              lng,
              // null = terminus de la tournée (l'école), cf. route_eta.dart
              cibleLat: versDomicile ? destLat : null,
              cibleLng: versDomicile ? destLng : null,
              distancePlanM: route.distancePlanM,
              dureePlanMin: route.dureePlanMin,
            )
          : null;
      try {
        final r = await Api.instance.predictEta(
          busLat: inputs == null ? lat : null,
          busLng: inputs == null ? lng : null,
          destLat: inputs == null ? destLat : null,
          destLng: inputs == null ? destLng : null,
          distanceRoutiereM: inputs?.distanceM,
          dureeBaseS: inputs?.dureeBaseS,
          moment: soir ? 'soir' : 'matin',
        );
        _etas[b.id] = r.etaMinutes;
        _versDomicile[b.id] = versDomicile;
      } catch (_) {
        /* ignore */
      }
    }
    if (mounted) setState(() {});
  }

  LatLng _lerp(LatLng a, LatLng b, double t) => LatLng(
    a.latitude + (b.latitude - a.latitude) * t,
    a.longitude + (b.longitude - a.longitude) * t,
  );

  /// Positions interpolées des bus des enfants (repli dernière position connue).
  Map<int, LatLng> _busPositions(ChildrenData data) {
    final out = <int, LatLng>{};
    for (final b in data.mesBus) {
      if (b.latitude != null && b.longitude != null) {
        out[b.id] = LatLng(b.latitude!, b.longitude!);
      }
    }
    for (final id in data.busIds) {
      final to = _to[id];
      if (to == null) continue;
      final from = _from[id] ?? to;
      out[id] = _lerp(from, to, _anim.value);
    }
    return out;
  }

  @override
  Widget build(BuildContext context) {
    final gps = ref.watch(gpsSocketProvider);
    _bind(gps);
    final async = ref.watch(childrenProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

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
        // Bus le plus proche de sa destination (celle qui concerne le parent).
        int? busProche;
        double? etaMin;
        for (final entry in _etas.entries) {
          if (etaMin == null || entry.value < etaMin) {
            etaMin = entry.value;
            busProche = entry.key;
          }
        }
        final etaLabel =
            busProche != null && (_versDomicile[busProche] ?? false)
            ? 'chez vous'
            : 'école';
        return Stack(
          children: [
            RepaintBoundary(
              child: AnimatedBuilder(
                animation: _anim,
                builder: (context, _) {
                  final busPos = _busPositions(data);
                  return FlutterMap(
                    mapController: _controller,
                    options: const MapOptions(
                      initialCenter: LatLng(Env.ecoleLat, Env.ecoleLng),
                      initialZoom: 13,
                      minZoom: 9,
                      maxZoom: 18,
                    ),
                    children: [
                      TileLayer(
                        urlTemplate: isDark
                            ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
                            : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
                        subdomains: const ['a', 'b', 'c', 'd'],
                        userAgentPackageName: 'ma.transport.parent_app',
                      ),
                      PolylineLayer(
                        polylines: [
                          for (final id in data.busIds)
                            if ((gps.trails[id]?.length ?? 0) > 1)
                              Polyline(
                                points: gps.trails[id]!,
                                strokeWidth: 3,
                                color: AppColors.brand.withValues(alpha: 0.45),
                              ),
                        ],
                      ),
                      MarkerLayer(
                        markers: [
                          const Marker(
                            point: LatLng(Env.ecoleLat, Env.ecoleLng),
                            width: 42,
                            height: 42,
                            child: _Pin(
                              icon: Icons.school_rounded,
                              color: AppColors.danger,
                            ),
                          ),
                          for (final e in data.enfants)
                            if (e.latitude != null && e.longitude != null)
                              Marker(
                                point: LatLng(e.latitude!, e.longitude!),
                                width: 30,
                                height: 30,
                                child: const _Pin(
                                  icon: Icons.home_rounded,
                                  color: AppColors.ok,
                                  size: 15,
                                ),
                              ),
                          for (final entry in busPos.entries)
                            Marker(
                              point: entry.value,
                              width: 46,
                              height: 46,
                              child: _BusMarker(
                                matricule:
                                    data.busById[entry.key]?.matricule ??
                                    '${entry.key}',
                                eta: _etas[entry.key],
                                versDomicile: _versDomicile[entry.key] ?? false,
                              ),
                            ),
                        ],
                      ),
                    ],
                  );
                },
              ),
            ),
            Positioned(
              top: AppSpacing.md,
              left: AppSpacing.md,
              right: AppSpacing.md,
              child: Row(
                children: [
                  _pill(
                    gps.connected ? 'GPS en direct' : 'hors ligne',
                    gps.connected ? AppColors.ok : context.softColor,
                    gps.connected
                        ? Icons.gps_fixed_rounded
                        : Icons.gps_off_rounded,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  if (etaMin != null)
                    _pill(
                      '~${etaMin.round()} min → $etaLabel',
                      AppColors.brand,
                      Icons.schedule_rounded,
                    ),
                ],
              ),
            ),
            Positioned(
              right: AppSpacing.lg,
              bottom: AppSpacing.lg,
              child: FloatingActionButton.small(
                heroTag: 'recenter',
                tooltip: 'Recentrer la carte sur le bus',
                backgroundColor: context.scheme.surface,
                foregroundColor: AppColors.brand,
                elevation: 2,
                onPressed: () {
                  final pos = _busPositions(data).values;
                  _controller.move(
                    pos.isNotEmpty
                        ? pos.first
                        : const LatLng(Env.ecoleLat, Env.ecoleLng),
                    14.5,
                  );
                },
                child: const Icon(Icons.my_location_rounded),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _pill(String text, Color color, IconData icon) {
    return Semantics(
      label: text,
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
        decoration: BoxDecoration(
          color: context.scheme.surface,
          borderRadius: BorderRadius.circular(AppRadius.pill),
          border: Border.all(color: context.borderColor),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.08),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 5),
            Text(
              text,
              style: TextStyle(
                color: color,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Pin extends StatelessWidget {
  final IconData icon;
  final Color color;
  final double size;
  const _Pin({required this.icon, required this.color, this.size = 22});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: context.scheme.surface,
        shape: BoxShape.circle,
        border: Border.all(color: color, width: 2.4),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.15),
            blurRadius: 4,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Icon(icon, color: color, size: size),
    );
  }
}

class _BusMarker extends StatelessWidget {
  final String matricule;
  final double? eta;
  final bool versDomicile;
  const _BusMarker({
    required this.matricule,
    this.eta,
    this.versDomicile = false,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message:
          'Bus $matricule'
          '${eta != null ? ' · ~${eta!.round()} min → ${versDomicile ? "chez vous" : "école"}' : ''}',
      child: Container(
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [AppColors.brand, Color(0xFF4F46E5)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.white, width: 2.5),
          boxShadow: [
            BoxShadow(
              color: AppColors.brand.withValues(alpha: 0.45),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: const Icon(
          Icons.directions_bus_rounded,
          color: Colors.white,
          size: 22,
        ),
      ),
    );
  }
}
