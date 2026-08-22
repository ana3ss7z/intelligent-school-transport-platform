/**
 * ETA « le long de la tournée » — distance restante sur le circuit réel, pas à vol d'oiseau.
 *
 * Pourquoi : la tournée MS5 est école → élèves (ordre) → école. Pendant le ramassage le bus
 * s'ÉLOIGNE de l'école, donc un ETA calculé en point-à-point (bus → école) AUGMENTE (3→4→7→9)
 * alors que le bus avance normalement. On projette donc la position GPS sur la polyligne figée
 * du trajet et on mesure ce qui reste À PARCOURIR jusqu'à la cible — une quantité qui décroît.
 *
 * Géométrie : projection équirectangulaire locale (lat de référence = 1er point). À l'échelle
 * d'une ville (Meknès, ~20 km), l'erreur est négligeable et on évite une dépendance.
 */

export type LatLng = { lat: number; lng: number };
/** Polyligne telle que renvoyée par MS5/MS1 : [[lat, lng], …]. */
export type Polyline = [number, number][];

const R = 6371000;
const toRad = (d: number) => (d * Math.PI) / 180;

/** Vitesse de repli si la tournée n'a pas de totaux OSRM : ~25 km/h en urbain. */
const VITESSE_DEFAUT_MS = 7;
/** Bornes de sécurité : un ratio distance/durée aberrant ne doit pas produire un ETA absurde. */
const VITESSE_MIN_MS = 2.5; // 9 km/h
const VITESSE_MAX_MS = 22; // 79 km/h

/** Projette en mètres autour d'une latitude de référence (x = est, y = nord). */
const projeter = (p: LatLng, lat0: number) => ({
  x: toRad(p.lng) * R * Math.cos(toRad(lat0)),
  y: toRad(p.lat) * R,
});

/** Position d'un point ramené sur la polyligne. */
export interface SnapResult {
  /** Distance parcourue depuis le début de la polyligne, en mètres. */
  alongM: number;
  /** Écart perpendiculaire à la polyligne, en mètres (qualité du recalage). */
  offsetM: number;
}

/**
 * Recale `point` sur `poly`.
 *
 * @param minAlongM ne considère que les projections situées au-delà de cette abscisse.
 *   Indispensable sur une tournée en boucle : l'école apparaît au début ET à la fin, et le
 *   domicile d'un élève peut être frôlé deux fois. On veut la prochaine occurrence DEVANT le bus.
 */
export function snapToRoute(poly: Polyline, point: LatLng, minAlongM = -1): SnapResult | null {
  if (poly.length < 2) return null;
  const lat0 = poly[0][0];
  const p = projeter(point, lat0);

  let cumul = 0;
  let best: SnapResult | null = null;
  let bestGlobal: SnapResult | null = null;

  for (let i = 0; i < poly.length - 1; i++) {
    const a = projeter({ lat: poly[i][0], lng: poly[i][1] }, lat0);
    const b = projeter({ lat: poly[i + 1][0], lng: poly[i + 1][1] }, lat0);
    const dx = b.x - a.x, dy = b.y - a.y;
    const len2 = dx * dx + dy * dy;
    const segLen = Math.sqrt(len2);

    // t = position relative de la projection sur le segment, bornée à [0,1]
    const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2));
    const projX = a.x + t * dx, projY = a.y + t * dy;
    const offsetM = Math.hypot(p.x - projX, p.y - projY);
    const alongM = cumul + t * segLen;

    const cand: SnapResult = { alongM, offsetM };
    if (!bestGlobal || offsetM < bestGlobal.offsetM) bestGlobal = cand;
    if (alongM >= minAlongM && (!best || offsetM < best.offsetM)) best = cand;

    cumul += segLen;
  }
  // Rien devant (cible déjà dépassée) → on rend la meilleure projection absolue.
  return best ?? bestGlobal;
}

/** Longueur totale de la polyligne, en mètres. */
export function longueurRoute(poly: Polyline): number {
  if (poly.length < 2) return 0;
  const lat0 = poly[0][0];
  let total = 0;
  for (let i = 0; i < poly.length - 1; i++) {
    const a = projeter({ lat: poly[i][0], lng: poly[i][1] }, lat0);
    const b = projeter({ lat: poly[i + 1][0], lng: poly[i + 1][1] }, lat0);
    total += Math.hypot(b.x - a.x, b.y - a.y);
  }
  return total;
}

/**
 * Distance restante le long de la tournée, du bus jusqu'à la cible.
 *
 * @param cible `"fin"` = terminus de la tournée (l'école : la boucle y revient, donc on vise
 *   explicitement la FIN et non les coordonnées de l'école, qui se projetteraient sur le départ).
 *   Sinon = un point du circuit (domicile de l'élève), cherché DEVANT le bus.
 * @param depuisAlongM abscisse déjà atteinte par le bus, à réinjecter d'un calcul au suivant.
 *
 *   **Pourquoi ce paramètre est nécessaire.** La tournée MS5 est un cycle FERMÉ : sur les données
 *   réelles du groupe 1, le premier et le dernier point sont à **0,0 m** l'un de l'autre. Quand le
 *   bus revient à l'école, sa position se recale aussi bien sur le début que sur la fin — et à
 *   égalité d'écart, c'est le début qui l'emporte. Mesuré sur la vraie tournée : à 98 % du parcours
 *   il reste 725 m (1,4 min), à 99 % il « reste » 18 837 m (35,4 min). Le compte à rebours bondit
 *   au moment exact de l'arrivée, sous les yeux des familles.
 *
 *   En mémorisant l'abscisse atteinte, on interdit ce retour en arrière — un bus ne rembobine pas
 *   sa tournée. Si le bus s'écarte vraiment de la route, `snapToRoute` retombe sur la meilleure
 *   projection absolue et l'ETA reste défini.
 * @returns mètres restants, ou null si la polyligne est inexploitable.
 */
export function distanceRestanteM(
  poly: Polyline,
  bus: LatLng,
  cible: LatLng | "fin",
  depuisAlongM = -1,
): number | null {
  const snapBus = snapToRoute(poly, bus, depuisAlongM);
  if (!snapBus) return null;

  if (cible === "fin") return Math.max(0, longueurRoute(poly) - snapBus.alongM);

  const snapCible = snapToRoute(poly, cible, snapBus.alongM);
  if (!snapCible) return null;
  return Math.max(0, snapCible.alongM - snapBus.alongM);
}

/**
 * Vitesse moyenne réelle du circuit, déduite des totaux OSRM figés au démarrage du trajet.
 * C'est ce qui permet de convertir « mètres restants » en « durée de base » sans deviner.
 */
export function vitesseCircuitMs(distancePlanM?: number | null, dureePlanMin?: number | null): number {
  if (!distancePlanM || !dureePlanMin || dureePlanMin <= 0) return VITESSE_DEFAUT_MS;
  const v = distancePlanM / (dureePlanMin * 60);
  return Math.max(VITESSE_MIN_MS, Math.min(VITESSE_MAX_MS, v));
}

/**
 * Entrées MS12 (`distance_routiere_m` + `duree_base_s`) pour la portion restante.
 *
 * `alongM` est renvoyé en plus : c'est l'abscisse mesurée du bus, à repasser en `depuisAlongM`
 * au calcul suivant pour que la progression ne puisse pas repartir en arrière.
 */
export function etaInputsRestants(
  poly: Polyline,
  bus: LatLng,
  cible: LatLng | "fin",
  distancePlanM?: number | null,
  dureePlanMin?: number | null,
  depuisAlongM = -1,
): { distance_routiere_m: number; duree_base_s: number; alongM: number } | null {
  const snapBus = snapToRoute(poly, bus, depuisAlongM);
  if (!snapBus) return null;

  const longueur = longueurRoute(poly);
  let restant: number;
  if (cible === "fin") {
    restant = Math.max(0, longueur - snapBus.alongM);
  } else {
    const snapCible = snapToRoute(poly, cible, snapBus.alongM);
    if (!snapCible) return null;
    restant = Math.max(0, snapCible.alongM - snapBus.alongM);
  }

  // Vitesse déduite de la polyligne RÉELLEMENT mesurée, et non du total annoncé.
  // Mesurer les mètres restants sur une géométrie puis les diviser par la vitesse d'une AUTRE est
  // incohérent par construction : au départ, l'ETA doit valoir exactement la durée annoncée de la
  // tournée. Ce n'était pas théorique — `distance_m` (matrice OSRM /table) et la polyligne (/route)
  // ont divergé de +11 % jusqu'au correctif de MS5 (`osrm_client.py`, `continue_straight=false`).
  const v = vitesseCircuitMs(longueur > 0 ? longueur : distancePlanM, dureePlanMin);
  return { distance_routiere_m: restant, duree_base_s: restant / v, alongM: snapBus.alongM };
}
