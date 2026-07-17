/** Préférences UI persistées (défauts du formulaire clustering). Côté client uniquement. */
export interface Prefs { capacity: number; rayon: number }

const KEY = "ts_prefs";
const DEFAULTS: Prefs = { capacity: 50, rayon: 0 };

export function getPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : DEFAULTS;
  } catch {
    return DEFAULTS;
  }
}

export function setPrefs(p: Prefs) {
  localStorage.setItem(KEY, JSON.stringify(p));
}
