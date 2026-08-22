import 'dart:math' as math;

/// ETA « le long de la tournée » — distance restante sur le circuit réel, pas à vol d'oiseau.
///
/// Pourquoi : la tournée MS5 est école → élèves (ordre) → école. Pendant le ramassage le bus
/// s'ÉLOIGNE de l'école, donc un ETA point-à-point (bus → école) AUGMENTE (3→4→7→9) alors que le
/// bus avance normalement. On projette la position GPS sur la polyligne figée du trajet et on
/// mesure ce qui reste À PARCOURIR jusqu'à la cible — une quantité qui décroît.
///
/// Jumeau Dart de `web-admin/src/lib/routeEta.ts` (même algorithme, mêmes constantes).

const double _r = 6371000;
double _toRad(double d) => d * math.pi / 180;

/// Vitesse de repli si la tournée n'a pas de totaux OSRM : ~25 km/h en urbain.
const double _vitesseDefautMs = 7;
const double _vitesseMinMs = 2.5; // 9 km/h
const double _vitesseMaxMs = 22; // 79 km/h

class _Pt {
  final double x, y;
  const _Pt(this.x, this.y);
}

/// Projection équirectangulaire locale (x = est, y = nord), en mètres.
_Pt _projeter(double lat, double lng, double lat0) =>
    _Pt(_toRad(lng) * _r * math.cos(_toRad(lat0)), _toRad(lat) * _r);

/// Position d'un point ramené sur la polyligne.
class SnapResult {
  /// Distance parcourue depuis le début de la polyligne, en mètres.
  final double alongM;

  /// Écart perpendiculaire à la polyligne, en mètres (qualité du recalage).
  final double offsetM;

  const SnapResult(this.alongM, this.offsetM);
}

/// Point d'une polyligne `[[lat, lng], …]` telle que renvoyée par MS1/MS5.
typedef RoutePolyline = List<List<double>>;

/// Recale (`lat`,`lng`) sur [poly].
///
/// [minAlongM] ne retient que les projections au-delà de cette abscisse : indispensable sur une
/// tournée en boucle, où l'école apparaît au début ET à la fin et où un domicile peut être frôlé
/// deux fois — on veut la prochaine occurrence DEVANT le bus.
SnapResult? snapToRoute(
  RoutePolyline poly,
  double lat,
  double lng, {
  double minAlongM = -1,
}) {
  if (poly.length < 2) return null;
  final lat0 = poly[0][0];
  final p = _projeter(lat, lng, lat0);

  double cumul = 0;
  SnapResult? best;
  SnapResult? bestGlobal;

  for (var i = 0; i < poly.length - 1; i++) {
    final a = _projeter(poly[i][0], poly[i][1], lat0);
    final b = _projeter(poly[i + 1][0], poly[i + 1][1], lat0);
    final dx = b.x - a.x, dy = b.y - a.y;
    final len2 = dx * dx + dy * dy;
    final segLen = math.sqrt(len2);

    // t = position relative de la projection sur le segment, bornée à [0,1]
    final t = len2 == 0
        ? 0.0
        : (((p.x - a.x) * dx + (p.y - a.y) * dy) / len2).clamp(0.0, 1.0);
    final offsetM = _hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
    final alongM = cumul + t * segLen;

    final cand = SnapResult(alongM, offsetM);
    if (bestGlobal == null || offsetM < bestGlobal.offsetM) bestGlobal = cand;
    if (alongM >= minAlongM && (best == null || offsetM < best.offsetM)) {
      best = cand;
    }
    cumul += segLen;
  }
  // Rien devant (cible déjà dépassée) → meilleure projection absolue.
  return best ?? bestGlobal;
}

double _hypot(double a, double b) => math.sqrt(a * a + b * b);

/// Longueur totale de la polyligne, en mètres.
double longueurRoute(RoutePolyline poly) {
  if (poly.length < 2) return 0;
  final lat0 = poly[0][0];
  double total = 0;
  for (var i = 0; i < poly.length - 1; i++) {
    final a = _projeter(poly[i][0], poly[i][1], lat0);
    final b = _projeter(poly[i + 1][0], poly[i + 1][1], lat0);
    total += _hypot(b.x - a.x, b.y - a.y);
  }
  return total;
}

/// Distance restante le long de la tournée, du bus jusqu'à la cible.
///
/// Si [cibleLat]/[cibleLng] sont nuls, la cible est le TERMINUS de la tournée (l'école : la boucle
/// y revient, donc viser explicitement la fin — les coordonnées de l'école se projetteraient sur
/// le point de départ). Retourne null si la polyligne est inexploitable.
///
/// [depuisAlongM] = abscisse déjà atteinte par le bus, à réinjecter d'un calcul au suivant.
///
/// **Pourquoi ce paramètre est nécessaire.** La tournée MS5 est un cycle FERMÉ : sur les données
/// réelles du groupe 1, le premier et le dernier point sont à **0,0 m** l'un de l'autre. Quand le
/// bus revient à l'école, sa position se recale donc aussi bien sur le début que sur la fin — et à
/// égalité d'écart c'est le début qui l'emporte. Mesuré sur la vraie tournée : à 98 % du parcours il
/// reste 725 m (1,4 min), à 99 % il « reste » 18 837 m (35,4 min). Le compte à rebours bondit au
/// moment exact de l'arrivée, côté chauffeur comme côté parents.
///
/// En mémorisant l'abscisse atteinte, on interdit ce retour en arrière — un bus ne rembobine pas sa
/// propre tournée. Effet de bord bienvenu : cela absorbe aussi les micro-reculs (quelques dizaines
/// de mètres) là où le circuit se frôle lui-même. Si le bus s'écarte vraiment de la route,
/// [snapToRoute] retombe sur la meilleure projection absolue et l'ETA reste défini.
double? distanceRestanteM(
  RoutePolyline poly,
  double busLat,
  double busLng, {
  double? cibleLat,
  double? cibleLng,
  double depuisAlongM = -1,
}) {
  final snapBus = snapToRoute(poly, busLat, busLng, minAlongM: depuisAlongM);
  if (snapBus == null) return null;

  if (cibleLat == null || cibleLng == null) {
    return math.max(0, longueurRoute(poly) - snapBus.alongM);
  }
  final snapCible = snapToRoute(
    poly,
    cibleLat,
    cibleLng,
    minAlongM: snapBus.alongM,
  );
  if (snapCible == null) return null;
  return math.max(0, snapCible.alongM - snapBus.alongM);
}

/// Vitesse moyenne réelle du circuit, déduite des totaux OSRM figés au démarrage du trajet.
/// C'est ce qui convertit « mètres restants » en « durée de base » sans deviner.
double vitesseCircuitMs(double? distancePlanM, double? dureePlanMin) {
  if (distancePlanM == null ||
      dureePlanMin == null ||
      distancePlanM <= 0 ||
      dureePlanMin <= 0) {
    return _vitesseDefautMs;
  }
  return (distancePlanM / (dureePlanMin * 60)).clamp(
    _vitesseMinMs,
    _vitesseMaxMs,
  );
}

/// Entrées MS12 (`distance_routiere_m` + `duree_base_s`) pour la portion restante.
class EtaInputs {
  final double distanceM;
  final double dureeBaseS;

  /// Abscisse du bus sur le circuit, à réinjecter en [depuisAlongM] au prochain
  /// calcul pour que la progression ne puisse pas repartir en arrière.
  final double alongM;

  const EtaInputs(this.distanceM, this.dureeBaseS, this.alongM);
}

EtaInputs? etaInputsRestants(
  RoutePolyline poly,
  double busLat,
  double busLng, {
  double? cibleLat,
  double? cibleLng,
  double? distancePlanM,
  double? dureePlanMin,
  double depuisAlongM = -1,
}) {
  final snapBus = snapToRoute(poly, busLat, busLng, minAlongM: depuisAlongM);
  if (snapBus == null) return null;

  final longueur = longueurRoute(poly);
  final double restant;
  if (cibleLat == null || cibleLng == null) {
    restant = math.max(0, longueur - snapBus.alongM);
  } else {
    final snapCible = snapToRoute(
      poly,
      cibleLat,
      cibleLng,
      minAlongM: snapBus.alongM,
    );
    if (snapCible == null) return null;
    restant = math.max(0, snapCible.alongM - snapBus.alongM);
  }

  // Vitesse déduite de la polyligne RÉELLEMENT mesurée, et non du total annoncé.
  // Mesurer les mètres restants sur une géométrie puis les diviser par la vitesse
  // d'une AUTRE est incohérent par construction : au départ, l'ETA doit valoir
  // exactement la durée annoncée de la tournée, et c'est ce que garantit cette
  // ligne. Ce n'était pas théorique — `distance_m` (matrice OSRM /table) et la
  // polyligne (/route) ont divergé de +11 % jusqu'au correctif de MS5
  // (`osrm_client.py`, `continue_straight=false`), ce qui gonflait l'ETA d'autant.
  // On garde cette source unique même maintenant que les deux convergent : elle
  // rend le calcul immunisé contre une nouvelle divergence.
  final v = vitesseCircuitMs(
    longueur > 0 ? longueur : distancePlanM,
    dureePlanMin,
  );
  return EtaInputs(restant, restant / v, snapBus.alongM);
}
