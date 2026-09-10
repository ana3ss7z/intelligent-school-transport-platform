// Palette « lignes » — couleurs fonctionnelles réutilisées pour clusters/bus/tournées.
export const LINE_COLORS = [
  "#2A6FDB", "#1FA37A", "#E4572E", "#6B4EFF", "#F2A900",
  "#D6336C", "#0CA6A6", "#8A6D3B", "#4C6EF5", "#12B886",
];

/** Couleur de « ligne » stable pour un id (groupe/bus). */
export const lineColor = (id: number | null | undefined) =>
  id == null ? "#9AA3B2" : LINE_COLORS[Math.abs(id) % LINE_COLORS.length];
