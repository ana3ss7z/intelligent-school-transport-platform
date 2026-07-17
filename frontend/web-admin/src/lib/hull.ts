export type LatLng = [number, number];

/** Enveloppe convexe (Andrew monotone chain) — points en [lat, lng]. */
export function convexHull(pts: LatLng[]): LatLng[] {
  if (pts.length < 3) return pts.slice();
  const p = pts.slice().sort((a, b) => (a[1] - b[1]) || (a[0] - b[0]));
  const cross = (o: LatLng, a: LatLng, b: LatLng) =>
    (a[1] - o[1]) * (b[0] - o[0]) - (a[0] - o[0]) * (b[1] - o[1]);
  const lo: LatLng[] = [];
  for (const q of p) { while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q); }
  const up: LatLng[] = [];
  for (let i = p.length - 1; i >= 0; i--) { const q = p[i]; while (up.length >= 2 && cross(up[up.length - 2], up[up.length - 1], q) <= 0) up.pop(); up.push(q); }
  lo.pop(); up.pop();
  return lo.concat(up);
}

/** Centroïde d'un nuage de points. */
export function centroid(pts: LatLng[]): LatLng {
  const n = pts.length || 1;
  return [pts.reduce((s, p) => s + p[0], 0) / n, pts.reduce((s, p) => s + p[1], 0) / n];
}

/** Gonfle un polygone autour d'un centre (facteur > 1 = marge autour des points). */
export function padPoly(poly: LatLng[], c: LatLng, f: number): LatLng[] {
  return poly.map((p) => [c[0] + (p[0] - c[0]) * f, c[1] + (p[1] - c[1]) * f] as LatLng);
}
