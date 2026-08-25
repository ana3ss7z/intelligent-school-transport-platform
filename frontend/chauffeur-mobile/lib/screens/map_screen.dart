import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../api/api_client.dart';
import '../config/env.dart';
import '../models/models.dart';
import '../services/gps_socket.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Carte de MON bus : position live, tracé de la tournée, arrêts numérotés.
///
/// Contrairement à la carte admin, un seul bus est affiché — celui du chauffeur
/// connecté. Le WebSocket MS3 diffuse toute la flotte, le filtrage est donc
/// côté client (le serveur ne garde qu'un seul filtre d'abonnement).
class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen>
    with SingleTickerProviderStateMixin {
  final _controller = MapController();

  /// Créé dans `initState`, et **surtout pas** en initialiseur `late final`.
  /// Un `late final` n'est évalué qu'au premier accès : si l'écran ne rend
  /// jamais la carte (chauffeur sans bus affecté, erreur de chargement), le
  /// premier accès est celui de `dispose()` — qui construit alors un `Ticker`
  /// sur un élément déjà désactivé et lève « Looking up a deactivated widget's
  /// ancestor is unsafe ». Le crash survient donc en quittant l'écran, pas en
  /// l'ouvrant.
  late final AnimationController _anim;

  GpsSocket? _gps;
  LatLng? _from;
  LatLng? _to;

  List<Eleve> _eleves = const [];
  TourneePlan? _plan;
  bool _chargement = true;
  bool _suivreBus = true;

  @override
  void initState() {
    super.initState();
    _anim = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    WidgetsBinding.instance.addPostFrameCallback((_) => _charger());
  }

  @override
  void dispose() {
    _gps?.removeListener(_onGps);
    _anim.dispose();
    super.dispose();
  }

  Future<void> _charger() async {
    final bus = await ref.read(myBusProvider.future);
    if (bus == null) {
      if (mounted) setState(() => _chargement = false);
      return;
    }
    final api = ref.read(apiProvider);
    try {
      final eleves = await api.getElevesParBus(bus.id);
      if (!mounted) return;
      setState(() => _eleves = eleves);

      // Tournée figée du trajet en cours si possible : c'est le tracé que MS11
      // surveille, donc le seul qui corresponde à ce qu'on affiche au chauffeur.
      TourneePlan? plan;
      try {
        final figee = await api.getTrajetRoute(bus.id);
        if (figee != null && figee.hasGeometrie) {
          plan = TourneePlan(
            geometrie: figee.geometrie,
            distanceM: figee.distancePlanM,
            dureeMin: figee.dureePlanMin,
            ordre: [for (final e in eleves) e.id],
          );
        }
      } catch (_) {
        // pas de trajet en cours → on planifie ci-dessous
      }

      if (plan == null) {
        final groupeId = eleves
            .map((e) => e.groupeId)
            .whereType<int>()
            .firstOrNull;
        if (groupeId != null) {
          final cache = ref.read(tourneeCacheProvider);
          try {
            plan = await api.getTournee(groupeId, 'matin');
            await cache.save(groupeId, 'matin', plan);
          } catch (_) {
            plan = await cache.load(groupeId, 'matin');
          }
        }
      }
      if (mounted) {
        setState(() {
          _plan = plan;
          _chargement = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _chargement = false);
    }
  }

  void _bind(GpsSocket gps) {
    if (identical(gps, _gps)) return;
    _gps?.removeListener(_onGps);
    _gps = gps..addListener(_onGps);
  }

  /// Nouvelle position → interpolation douce depuis la précédente.
  ///
  /// Les pings MS3 arrivent toutes les quelques secondes ; sans interpolation le
  /// marqueur « saute », ce qui se lit comme un bug alors que c'est le rythme
  /// normal du GPS.
  void _onGps() {
    final bus = ref.read(myBusProvider).value;
    final gps = _gps;
    if (bus == null || gps == null) return;
    final p = gps.positions[bus.id];
    if (p == null) return;
    final cible = LatLng(p.latitude, p.longitude);
    _from = _to ?? cible;
    _to = cible;
    if (mounted) {
      _anim.forward(from: 0);
      if (_suivreBus) _controller.move(cible, _controller.camera.zoom);
      setState(() {});
    }
  }

  LatLng? _positionBus(Bus bus) {
    final to = _to;
    if (to != null) {
      final from = _from ?? to;
      final t = _anim.value;
      return LatLng(
        from.latitude + (to.latitude - from.latitude) * t,
        from.longitude + (to.longitude - from.longitude) * t,
      );
    }
    if (bus.latitude != null && bus.longitude != null) {
      return LatLng(bus.latitude!, bus.longitude!);
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final gps = ref.watch(gpsSocketProvider);
    _bind(gps);
    final busAsync = ref.watch(myBusProvider);
    final sombre = Theme.of(context).brightness == Brightness.dark;

    return busAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => ErrorRetry(
        message: friendlyError(e),
        onRetry: () => ref.invalidate(myBusProvider),
      ),
      data: (bus) {
        if (bus == null) {
          return const EmptyState(
            icon: Icons.no_transfer_outlined,
            text: 'Aucun bus ne vous est affecté.',
          );
        }
        final ordre = _plan?.ordre ?? const <int>[];
        final rangs = {for (var i = 0; i < ordre.length; i++) ordre[i]: i + 1};

        return Stack(
          children: [
            RepaintBoundary(
              child: AnimatedBuilder(
                animation: _anim,
                builder: (context, _) {
                  final position = _positionBus(bus);
                  return FlutterMap(
                    mapController: _controller,
                    options: MapOptions(
                      // Plus `const` : les coordonnées de l'école viennent de MS13 et ne sont
                      // donc plus connues à la compilation.
                      initialCenter:
                          position ?? LatLng(Env.ecoleLat, Env.ecoleLng),
                      initialZoom: 13,
                      minZoom: 9,
                      maxZoom: 18,
                      // Toucher la carte = reprendre la main sur le cadrage.
                      onPointerDown: (_, _) {
                        if (_suivreBus) setState(() => _suivreBus = false);
                      },
                    ),
                    children: [
                      TileLayer(
                        urlTemplate: sombre
                            ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
                            : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
                        subdomains: const ['a', 'b', 'c', 'd'],
                        userAgentPackageName: 'ma.transport.chauffeur_app',
                      ),
                      if ((_plan?.geometrie.length ?? 0) > 1)
                        PolylineLayer(
                          polylines: [
                            Polyline(
                              points: [
                                for (final p in _plan!.geometrie)
                                  LatLng(p[0], p[1]),
                              ],
                              strokeWidth: 4,
                              color: AppColors.route.withValues(alpha: 0.55),
                            ),
                          ],
                        ),
                      if ((gps.trails[bus.id]?.length ?? 0) > 1)
                        PolylineLayer(
                          polylines: [
                            Polyline(
                              points: gps.trails[bus.id]!,
                              strokeWidth: 3,
                              color: AppColors.driver,
                            ),
                          ],
                        ),
                      MarkerLayer(
                        markers: [
                          Marker(
                            point: LatLng(Env.ecoleLat, Env.ecoleLng),
                            width: 40,
                            height: 40,
                            child: _Pin(
                              icon: Icons.school_rounded,
                              color: AppColors.danger,
                            ),
                          ),
                          for (final e in _eleves)
                            if (e.latitude != null && e.longitude != null)
                              Marker(
                                point: LatLng(e.latitude!, e.longitude!),
                                width: 26,
                                height: 26,
                                child: _Arret(
                                  rang: rangs[e.id] ?? e.ordrePassage,
                                  fait: e.statutPresence,
                                ),
                              ),
                          if (position != null)
                            Marker(
                              point: position,
                              width: 48,
                              height: 48,
                              child: _MarqueurBus(matricule: bus.matricule),
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
              child: _Pilule(connecte: gps.connected, chargement: _chargement),
            ),
            Positioned(
              right: AppSpacing.md,
              bottom: AppSpacing.xl,
              child: Column(
                children: [
                  FloatingActionButton.small(
                    heroTag: 'suivre',
                    tooltip: _suivreBus
                        ? 'Suivi automatique actif'
                        : 'Recentrer sur mon bus',
                    backgroundColor: _suivreBus ? AppColors.route : null,
                    foregroundColor: _suivreBus ? Colors.white : null,
                    onPressed: () {
                      final p = _positionBus(bus);
                      setState(() => _suivreBus = true);
                      if (p != null) _controller.move(p, 15);
                    },
                    child: const Icon(Icons.my_location_rounded),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  FloatingActionButton.small(
                    heroTag: 'tournee',
                    tooltip: 'Voir toute la tournée',
                    onPressed: () {
                      final pts = [
                        for (final p
                            in _plan?.geometrie ?? const <List<double>>[])
                          LatLng(p[0], p[1]),
                      ];
                      if (pts.length < 2) return;
                      setState(() => _suivreBus = false);
                      _controller.fitCamera(
                        CameraFit.coordinates(
                          coordinates: pts,
                          padding: const EdgeInsets.all(40),
                        ),
                      );
                    },
                    child: const Icon(Icons.zoom_out_map_rounded),
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

class _Pilule extends StatelessWidget {
  const _Pilule({required this.connecte, required this.chargement});
  final bool connecte;
  final bool chargement;

  @override
  Widget build(BuildContext context) {
    final couleur = connecte ? AppColors.ok : AppColors.warn;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor.withValues(alpha: 0.94),
        borderRadius: BorderRadius.circular(AppRadius.pill),
        border: Border.all(color: context.borderColor),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            connecte ? Icons.podcasts_rounded : Icons.wifi_off_rounded,
            size: 14,
            color: couleur,
          ),
          const SizedBox(width: 6),
          Text(
            chargement
                ? 'Chargement…'
                : (connecte ? 'GPS en direct' : 'hors ligne'),
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: couleur,
            ),
          ),
        ],
      ),
    );
  }
}

class _Pin extends StatelessWidget {
  const _Pin({required this.icon, required this.color});
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 2),
      ),
      child: Icon(icon, size: 18, color: Colors.white),
    );
  }
}

/// Arrêt élève : numéro d'ordre, vert une fois traité.
class _Arret extends StatelessWidget {
  const _Arret({required this.rang, required this.fait});
  final int? rang;
  final bool fait;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Arrêt ${rang ?? '?'}${fait ? ', fait' : ''}',
      child: Container(
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: fait ? AppColors.ok : Colors.white,
          shape: BoxShape.circle,
          border: Border.all(
            color: fait ? AppColors.ok : AppColors.route,
            width: 2,
          ),
        ),
        child: Text(
          '${rang ?? '·'}',
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w800,
            color: fait ? Colors.white : AppColors.route,
          ),
        ),
      ),
    );
  }
}

class _MarqueurBus extends StatelessWidget {
  const _MarqueurBus({required this.matricule});
  final String matricule;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Mon bus $matricule',
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.driver,
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white, width: 3),
          boxShadow: [
            BoxShadow(
              color: AppColors.driver.withValues(alpha: 0.45),
              blurRadius: 12,
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
