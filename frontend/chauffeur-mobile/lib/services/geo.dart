import 'dart:math' as math;

const _rayonTerreM = 6371000.0;

double _rad(double d) => d * math.pi / 180;

/// Distance à vol d'oiseau, en mètres (haversine).
///
/// Réservée à l'affichage « prochain arrêt à ~N m » : c'est une indication de
/// proximité, pas une durée. Pour tout ce qui ressemble à un ETA, passer par
/// `route_eta.dart` (distance le long du circuit) — un vol d'oiseau vers une
/// cible que la tournée contourne donne des chiffres qui augmentent.
double distanceHaversineM(double lat1, double lng1, double lat2, double lng2) {
  final dLat = _rad(lat2 - lat1);
  final dLng = _rad(lng2 - lng1);
  final a =
      math.sin(dLat / 2) * math.sin(dLat / 2) +
      math.cos(_rad(lat1)) *
          math.cos(_rad(lat2)) *
          math.sin(dLng / 2) *
          math.sin(dLng / 2);
  return 2 * _rayonTerreM * math.asin(math.min(1, math.sqrt(a)));
}
