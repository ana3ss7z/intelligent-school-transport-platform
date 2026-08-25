import { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";
import type { ReactNode } from "react";
import { getParametres } from "../api/endpoints";
import type { Parametre } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";

/**
 * Paramètres applicatifs servis par MS13.
 * =======================================
 *
 * Remplace `lib/prefs.ts` (qui n'écrivait que dans le localStorage du navigateur : le réglage
 * ne quittait jamais le poste de l'administrateur) et les intervalles de rafraîchissement qui
 * étaient écrits en dur dans une vingtaine de fichiers.
 *
 * Les valeurs sont rechargées toutes les 60 secondes. Un changement fait par un administrateur
 * atteint donc les autres postes — y compris les espaces parent et chauffeur — sans que
 * personne n'ait à recharger sa page.
 *
 * Les défauts ci-dessous ne dupliquent pas la configuration : ils ne servent qu'au premier
 * rendu, avant la réponse de MS13, et si le service est injoignable. L'interface reste
 * utilisable dans ce cas — c'est le même choix qu'en Python et dans MS4.
 */

export interface ParamsValeurs {
  ecole: { nom: string; lat: number; lng: number };
  ui: {
    pollTrajetMs: number;
    pollEtaMs: number;
    pollInboxMs: number;
    pollUnreadMs: number;
    pollListeMs: number;
    carteZoom: number;
    pageSize: number;
  };
  clustering: { capacity: number; rayon: number };
}

const DEFAUTS: ParamsValeurs = {
  ecole: { nom: "École Al Massira", lat: 33.893, lng: -5.5455 },
  ui: {
    pollTrajetMs: 15000, pollEtaMs: 30000, pollInboxMs: 15000,
    pollUnreadMs: 20000, pollListeMs: 10000, carteZoom: 13, pageSize: 25,
  },
  clustering: { capacity: 50, rayon: 0 },
};

interface ParamsState extends ParamsValeurs {
  /** Liste brute — utilisée par la page de configuration. */
  brut: Parametre[];
  chargement: boolean;
  /** À appeler après un enregistrement pour propager sans attendre le prochain cycle. */
  recharger: () => Promise<void>;
}

const Ctx = createContext<ParamsState | null>(null);

const RAFRAICHISSEMENT_MS = 60_000;

function nombre(m: Map<string, string>, cle: string, defaut: number): number {
  const v = m.get(cle);
  if (v === undefined || v === "") return defaut;
  const n = Number(v);
  return Number.isFinite(n) ? n : defaut;
}

function texte(m: Map<string, string>, cle: string, defaut: string): string {
  const v = m.get(cle);
  return v === undefined || v === "" ? defaut : v;
}

/** Secondes côté serveur (unité lisible par l'administrateur) → millisecondes côté React. */
function secondes(m: Map<string, string>, cle: string, defautMs: number): number {
  const s = nombre(m, cle, defautMs / 1000);
  // Garde-fou client, en plus de la borne serveur : un intervalle trop court multiplié par le
  // nombre d'onglets ouverts se heurterait au plafond de 20 requêtes/s de la passerelle.
  return Math.max(5, s) * 1000;
}

function assembler(liste: Parametre[]): ParamsValeurs {
  const m = new Map(liste.map((p) => [p.cle, p.valeur]));
  return {
    ecole: {
      nom: texte(m, "ecole.nom", DEFAUTS.ecole.nom),
      lat: nombre(m, "ecole.lat", DEFAUTS.ecole.lat),
      lng: nombre(m, "ecole.lng", DEFAUTS.ecole.lng),
    },
    ui: {
      pollTrajetMs: secondes(m, "ui.poll_trajet_s", DEFAUTS.ui.pollTrajetMs),
      pollEtaMs: secondes(m, "ui.poll_eta_s", DEFAUTS.ui.pollEtaMs),
      pollInboxMs: secondes(m, "ui.poll_inbox_s", DEFAUTS.ui.pollInboxMs),
      pollUnreadMs: secondes(m, "ui.poll_unread_s", DEFAUTS.ui.pollUnreadMs),
      pollListeMs: secondes(m, "ui.poll_liste_s", DEFAUTS.ui.pollListeMs),
      carteZoom: nombre(m, "ui.carte_zoom", DEFAUTS.ui.carteZoom),
      pageSize: nombre(m, "ui.page_size", DEFAUTS.ui.pageSize),
    },
    clustering: {
      capacity: nombre(m, "ms6.bus_capacity", DEFAUTS.clustering.capacity),
      rayon: nombre(m, "ms6.rayon_max_m", DEFAUTS.clustering.rayon),
    },
  };
}

export function ParamsProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [brut, setBrut] = useState<Parametre[]>([]);
  const [chargement, setChargement] = useState(true);

  const recharger = useCallback(async () => {
    // La route exige un jeton (tout rôle). Sans session, on garde les défauts : la page de
    // connexion ne doit pas déclencher un 401 en boucle.
    if (!token) { setChargement(false); return; }
    try {
      setBrut(await getParametres());
    } catch {
      // Silencieux et sans conséquence visible : les défauts restent en place. Une bannière
      // d'erreur ici serait du bruit sur toutes les pages pour un service non critique.
    } finally {
      setChargement(false);
    }
  }, [token]);

  useEffect(() => {
    recharger();
    const t = setInterval(() => { if (!document.hidden) recharger(); }, RAFRAICHISSEMENT_MS);
    return () => clearInterval(t);
  }, [recharger]);

  const value = useMemo<ParamsState>(
    () => ({ ...assembler(brut), brut, chargement, recharger }),
    [brut, chargement, recharger],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/**
 * Accès aux paramètres. Ne lève jamais hors du fournisseur : renvoie les défauts.
 *
 * Ce choix est délibéré — ce hook est appelé depuis des composants montés dans des contextes
 * variés (dialogues, cartes, écrans chauffeur). Une exception y transformerait un service de
 * configuration indisponible en écran blanc.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useParams(): ParamsState {
  const c = useContext(Ctx);
  if (c) return c;
  return { ...DEFAUTS, brut: [], chargement: false, recharger: async () => {} };
}
