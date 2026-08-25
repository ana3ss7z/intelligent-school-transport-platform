import { useEffect, useMemo, useState } from "react";
import { Save, RotateCcw, AlertTriangle, Check, Loader2, Eye, EyeOff, Zap, Lock } from "lucide-react";
import {
  getParametresSchema, updateParametres, resetParametres, verifierModelesLlm,
} from "../api/endpoints";
import type { Parametre, ParametreSchema, ModelesCheck } from "../api/endpoints";
import { useParams } from "../params/ParamsContext";
import { useToast } from "../components/Toast";
import { Panel, Button, StatusChip, Spinner } from "../components/ui";

/**
 * Console de configuration — pilote MS13.
 * =======================================
 *
 * Aucun libellé, borne ni valeur permise n'est écrit ici : tout vient de
 * `GET /api/parametres/schema`. Ajouter un réglage côté serveur le fait apparaître dans
 * cette page sans toucher au front — c'était la condition pour que la page reste juste
 * quand la configuration évolue.
 */

// Onglets : titre + sous-titre. Le contenu, lui, est entièrement piloté par le serveur.
const ONGLETS: Record<string, { titre: string; sous: string }> = {
  ECOLE:         { titre: "École",          sous: "Position de l'établissement et rayon de détection d'arrivée" },
  REGROUPEMENT:  { titre: "Regroupement",   sous: "Affectation des élèves aux bus (MS6) et garde-fou qualité" },
  TOURNEES:      { titre: "Tournées",       sous: "Optimisation de l'ordre de passage (MS5)" },
  ETA:           { titre: "Arrivées",       sous: "Prédiction et alertes d'arrivée imminente (MS12)" },
  CONTEXTE_PRED: { titre: "Contexte",       sous: "Météo, trafic et calendrier : automatiques ou imposés" },
  ANOMALIES:     { titre: "Anomalies",      sous: "Seuils de surveillance des trajets en cours (MS11)" },
  NOTIFICATIONS: { titre: "Notifications",  sous: "Ce qui est envoyé aux familles et à l'administration (MS4)" },
  ASSISTANT:     { titre: "Assistant",      sous: "Modèles, clés API et réglages de l'agent conversationnel (MS9)" },
  INTERFACE:     { titre: "Interface",      sous: "Rafraîchissement et affichage, dans le web et les applications" },
};

const IMPACT: Record<string, { label: string; tone: "ok" | "warn" | "line2" | "alert" }> = {
  IMMEDIAT:        { label: "immédiat",        tone: "ok" },
  PROCHAIN_CALCUL: { label: "prochain calcul", tone: "warn" },
  PROCHAIN_TRAJET: { label: "prochain trajet", tone: "warn" },
  REDEMARRAGE:     { label: "redémarrage",     tone: "alert" },
};

/**
 * Réglages qui redistribuent les élèves entre bus.
 *
 * Deux effets mesurés justifient l'avertissement : un changement de capacité ou de rayon
 * déplace ~7 % des élèves au recalcul suivant, et il invalide la référence du garde-fou
 * qualité, qui enregistre ces deux paramètres dans son contexte.
 */
const STRUCTURANTS = new Set(["ms6.bus_capacity", "ms6.rayon_max_m"]);

const champ =
  "w-full rounded-lg border border-line bg-panel px-3 py-2 tabular text-sm outline-none " +
  "focus:border-route disabled:opacity-50 disabled:cursor-not-allowed";

export function Settings() {
  const toast = useToast();
  const { recharger } = useParams();
  const [schema, setSchema] = useState<ParametreSchema | null>(null);
  const [onglet, setOnglet] = useState<string>("ECOLE");
  const [brouillon, setBrouillon] = useState<Record<string, string>>({});
  const [secretsVisibles, setSecretsVisibles] = useState<Record<string, boolean>>({});
  const [enregistrement, setEnregistrement] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [modeles, setModeles] = useState<ModelesCheck | null>(null);
  const [verifEnCours, setVerifEnCours] = useState(false);

  const charger = async () => {
    try {
      const s = await getParametresSchema();
      setSchema(s);
      if (!s.groupes.includes(onglet)) setOnglet(s.groupes[0]);
    } catch (e: unknown) {
      setErreur((e as { message?: string })?.message ?? "Chargement impossible");
    }
  };

  useEffect(() => { charger(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const params = useMemo(() => schema?.parametres[onglet] ?? [], [schema, onglet]);

  /**
   * Valeur affichée. Un secret n'est JAMAIS pré-rempli avec son masque : le champ reste vide,
   * avec « valeur enregistrée » en indication. Coller le masque dans le champ reviendrait à
   * proposer à l'administrateur de réécrire des puces à la place de sa clé.
   * (Le serveur refuse de toute façon d'écrire une valeur commençant par le caractère de masque.)
   */
  const valeurAffichee = (p: Parametre) =>
    brouillon[p.cle] ?? (p.type === "SECRET" ? "" : p.valeur);

  const modifie = (p: Parametre) => brouillon[p.cle] !== undefined && brouillon[p.cle] !== p.valeur;
  const nbModifs = params.filter(modifie).length;

  /**
   * Un réglage conditionnel est-il actif ?
   *
   * La condition est évaluée sur **l'état courant du formulaire** (`brouillon` d'abord, valeur
   * enregistrée ensuite), et non sur ce qui est en base. C'est ce qui permet de basculer le mode
   * sur « manuel » et de voir les champs se déverrouiller aussitôt, sans passer par un
   * enregistrement intermédiaire.
   *
   * Le réglage dont dépend celui-ci est cherché dans tout le schéma, pas seulement dans l'onglet
   * courant : rien n'oblige les deux à cohabiter (la clé TomTom est dans « Arrivées », la source
   * de trafic aussi, mais une dépendance inter-onglets doit rester possible).
   */
  const conditionRemplie = (p: Parametre): boolean => {
    if (!p.dependDe) return true;
    const source = schema
      ? Object.values(schema.parametres).flat().find((q) => q.cle === p.dependDe)
      : undefined;
    const courant = brouillon[p.dependDe] ?? source?.valeur;
    return courant === p.dependValeur;
  };

  /** Libellé du réglage dont dépend celui-ci — pour expliquer le verrou en français. */
  const libelleSource = (cle: string) =>
    (schema ? Object.values(schema.parametres).flat().find((q) => q.cle === cle) : undefined)
      ?.libelle ?? cle;

  const set = (cle: string, v: string) => setBrouillon((b) => ({ ...b, [cle]: v }));

  const enregistrer = async () => {
    // On n'envoie que ce qui a changé — inutile de réécrire 50 lignes pour un seuil.
    const aEnvoyer: Record<string, string> = {};
    for (const p of params) if (modifie(p)) aEnvoyer[p.cle] = brouillon[p.cle];
    if (Object.keys(aEnvoyer).length === 0) return;

    const structurants = Object.keys(aEnvoyer).filter((c) => STRUCTURANTS.has(c));
    if (structurants.length > 0) {
      const ok = window.confirm(
        "Ces réglages déterminent la composition des groupes.\n\n" +
        "Au prochain recalcul du regroupement, des élèves changeront de bus — environ 7 % " +
        "d'entre eux lors d'un changement de ce type. La référence du garde-fou qualité sera " +
        "également invalidée, puisqu'elle enregistre la capacité et le rayon.\n\n" +
        "Rien n'est appliqué tant que le regroupement n'est pas relancé depuis la page " +
        "Clustering. Enregistrer la nouvelle valeur ?",
      );
      if (!ok) return;
    }

    setEnregistrement(true);
    setErreur(null);
    try {
      const res = await updateParametres(aEnvoyer);
      setBrouillon({});
      await charger();
      await recharger();       // propage aux autres écrans sans attendre le cycle de 60 s
      toast.success(res.n === 0 ? "Aucun changement" : `${res.n} paramètre(s) enregistré(s)`);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error
        ?? "Enregistrement refusé";
      setErreur(msg);
      toast.error(msg);
    } finally {
      setEnregistrement(false);
    }
  };

  const reinitialiser = async () => {
    if (!window.confirm(`Remettre tous les réglages de « ${ONGLETS[onglet]?.titre ?? onglet} » ` +
                        "à leur valeur par défaut ?")) return;
    try {
      const res = await resetParametres({ groupe: onglet });
      setBrouillon({});
      await charger();
      await recharger();
      toast.success(`${res.n} paramètre(s) réinitialisé(s)`);
    } catch {
      toast.error("Réinitialisation impossible");
    }
  };

  const verifierModeles = async () => {
    setVerifEnCours(true);
    try {
      setModeles(await verifierModelesLlm());
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "MS9 injoignable";
      toast.error(`Vérification impossible : ${msg}`);
    } finally {
      setVerifEnCours(false);
    }
  };

  if (erreur && !schema) {
    return (
      <Panel className="p-6 max-w-2xl">
        <div className="flex items-start gap-3">
          <AlertTriangle size={18} className="text-alert mt-0.5 shrink-0" />
          <div>
            <p className="text-sm">Le service de configuration (MS13) est injoignable.</p>
            <p className="text-xs text-ink-soft mt-1">
              Les autres écrans continuent de fonctionner avec les valeurs par défaut. {erreur}
            </p>
          </div>
        </div>
      </Panel>
    );
  }
  if (!schema) return <Spinner label="Chargement du catalogue…" />;

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h1 className="text-2xl">Paramètres</h1>
        <p className="text-ink-soft text-sm">
          {schema.total} réglages appliqués à l'ensemble du système — services, console et
          applications mobiles. Les changements prennent effet sans redémarrage.
        </p>
      </div>

      {/* Onglets */}
      <div className="flex flex-wrap gap-1.5 border-b border-line pb-2" role="tablist">
        {schema.groupes.map((g) => (
          <button
            key={g}
            role="tab"
            aria-selected={onglet === g}
            onClick={() => { setBrouillon({}); setOnglet(g); }}
            className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
              onglet === g
                ? "bg-route text-white"
                : "text-ink-soft hover:text-ink hover:bg-line/40"
            }`}
          >
            {ONGLETS[g]?.titre ?? g}
          </button>
        ))}
      </div>

      <Panel className="p-4">
        <div className="mb-4">
          <h2 className="text-lg">{ONGLETS[onglet]?.titre ?? onglet}</h2>
          {ONGLETS[onglet]?.sous && (
            <p className="text-sm text-ink-soft mt-0.5">{ONGLETS[onglet].sous}</p>
          )}
        </div>

        <div className="divide-y divide-line">
          {params.map((p) => (
            <ChampParametre
              key={p.cle}
              p={p}
              valeur={valeurAffichee(p)}
              modifie={modifie(p)}
              actif={conditionRemplie(p)}
              libelleSource={p.dependDe ? libelleSource(p.dependDe) : ""}
              secretVisible={!!secretsVisibles[p.cle]}
              onBasculerSecret={() =>
                setSecretsVisibles((s) => ({ ...s, [p.cle]: !s[p.cle] }))}
              onChange={(v) => set(p.cle, v)}
            />
          ))}
        </div>

        {onglet === "ASSISTANT" && (
          <BlocModeles
            resultat={modeles}
            enCours={verifEnCours}
            onVerifier={verifierModeles}
          />
        )}

        {erreur && (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-alert/40 bg-alert/10 p-3 text-sm">
            <AlertTriangle size={16} className="text-alert mt-0.5 shrink-0" />
            <div>
              <p>{erreur}</p>
              <p className="text-xs text-ink-soft mt-1">
                Aucune valeur n'a été enregistrée : le lot est validé en bloc.
              </p>
            </div>
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-line pt-4">
          <Button onClick={enregistrer} disabled={nbModifs === 0 || enregistrement}>
            {enregistrement ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {nbModifs === 0 ? "Enregistrer" : `Enregistrer (${nbModifs})`}
          </Button>
          <Button onClick={reinitialiser} variant="ghost" tone="line2" disabled={enregistrement}>
            <RotateCcw size={16} /> Valeurs par défaut
          </Button>
          {nbModifs > 0 && (
            <span className="text-xs text-ink-soft">
              {nbModifs} modification{nbModifs > 1 ? "s" : ""} non enregistrée
              {nbModifs > 1 ? "s" : ""}
            </span>
          )}
        </div>
      </Panel>
    </div>
  );
}

// ── Un réglage ───────────────────────────────────────────────────────────────

function ChampParametre({
  p, valeur, modifie, actif, libelleSource, secretVisible, onBasculerSecret, onChange,
}: {
  p: Parametre; valeur: string; modifie: boolean; actif: boolean; libelleSource: string;
  secretVisible: boolean; onBasculerSecret: () => void; onChange: (v: string) => void;
}) {
  const impact = IMPACT[p.impact];
  const id = `param-${p.cle}`;

  // Seul le widget est atténué, pas le bloc entier : la phrase qui explique le verrou doit
  // rester parfaitement lisible — c'est elle qui dit quoi faire pour déverrouiller. Atténuer
  // le conteneur aurait aussi cumulé son opacité avec celle du champ désactivé.
  return (
    <div className="py-4 grid gap-3 md:grid-cols-[1fr_16rem] md:items-start">
      <div className="min-w-0">
        <label htmlFor={id} className="text-sm font-medium flex flex-wrap items-center gap-2">
          {p.libelle}
          {!actif && (
            <StatusChip tone="line2">
              <Lock size={11} className="inline -mt-0.5 mr-1" aria-hidden="true" />
              inactif
            </StatusChip>
          )}
          {modifie && <StatusChip tone="warn">non enregistré</StatusChip>}
          {!modifie && p.modifie && <StatusChip tone="line2">personnalisé</StatusChip>}
          {impact && p.impact !== "IMMEDIAT" && (
            <StatusChip tone={impact.tone}>{impact.label}</StatusChip>
          )}
        </label>
        {p.description && (
          <p className="text-xs text-ink-soft mt-1 leading-relaxed">{p.description}</p>
        )}
        {/*
          Le verrou n'est pas qu'un grisage : sans phrase, l'admin ne saurait pas quoi changer
          pour rendre le champ modifiable. On nomme le réglage à basculer et la valeur attendue.
        */}
        {!actif && (
          <p className="text-xs text-warn mt-1.5 flex items-start gap-1.5">
            <Lock size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>
              Sans effet tant que « {libelleSource} » n'est pas réglé sur
              {" "}<span className="font-mono">{p.dependValeur}</span>.
            </span>
          </p>
        )}
        <p className="text-[11px] font-mono text-ink-soft/70 mt-1.5">
          {p.cle}
          {p.type === "NUMBER" && p.min !== null && p.max !== null && (
            <> · de {p.min} à {p.max}</>
          )}
          {p.type !== "SECRET" && <> · défaut {p.valeurDefaut || "—"}</>}
          {p.modifiePar && <> · modifié par {p.modifiePar}</>}
        </p>
      </div>

      <div className="flex items-center gap-2">
        {p.type === "BOOLEAN" ? (
          <label className="inline-flex items-center gap-2 cursor-pointer text-sm">
            <input
              id={id} type="checkbox" checked={valeur === "true"}
              disabled={!actif}
              onChange={(e) => onChange(e.target.checked ? "true" : "false")}
              className="size-4 accent-(--route) disabled:cursor-not-allowed"
            />
            <span className="text-ink-soft">{valeur === "true" ? "Activé" : "Désactivé"}</span>
          </label>
        ) : p.type === "ENUM" ? (
          <select id={id} value={valeur} disabled={!actif}
                  onChange={(e) => onChange(e.target.value)} className={champ}>
            {(p.options ?? "").split(",").map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        ) : p.type === "SECRET" ? (
          <div className="w-full">
            <div className="relative">
              <input
                id={id}
                type={secretVisible ? "text" : "password"}
                value={valeur}
                disabled={!actif}
                onChange={(e) => onChange(e.target.value)}
                placeholder={p.defini ? "valeur enregistrée — laisser vide" : "non renseignée"}
                autoComplete="off" spellCheck={false}
                className={`${champ} pr-9`}
              />
              <button
                type="button" onClick={onBasculerSecret}
                aria-label={secretVisible ? "Masquer" : "Afficher"}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-soft hover:text-ink"
              >
                {secretVisible ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
            <p className="text-[11px] text-ink-soft mt-1">
              {p.defini
                ? "Un champ vide conserve la clé actuelle."
                : "Aucune clé enregistrée."}
            </p>
          </div>
        ) : (
          <div className="flex w-full items-center gap-2">
            <input
              id={id}
              type={p.type === "NUMBER" ? "number" : "text"}
              value={valeur}
              min={p.min ?? undefined}
              max={p.max ?? undefined}
              step={p.type === "NUMBER" ? "any" : undefined}
              disabled={!actif}
              onChange={(e) => onChange(e.target.value)}
              className={champ}
            />
            {p.unite && <span className="text-sm text-ink-soft shrink-0">{p.unite}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Vérification des modèles LLM ─────────────────────────────────────────────

/**
 * Confronte la cascade configurée à ce que servent réellement les fournisseurs.
 *
 * Un modèle retiré du service ne se voit pas depuis l'application : la cascade bascule
 * sur l'étage suivant et l'assistant continue de répondre. C'est ainsi que MS9 a tourné
 * plusieurs semaines sans repli, son dernier étage répondant 404 à chaque appel.
 */
function BlocModeles({
  resultat, enCours, onVerifier,
}: { resultat: ModelesCheck | null; enCours: boolean; onVerifier: () => void }) {
  return (
    <div className="mt-5 rounded-lg border border-line p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium">Disponibilité des modèles</h3>
          <p className="text-xs text-ink-soft mt-0.5">
            Interroge chaque fournisseur et vérifie que les modèles configurés sont toujours
            servis. À jouer avant une démonstration.
          </p>
        </div>
        <Button onClick={onVerifier} variant="ghost" disabled={enCours}>
          {enCours ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
          Vérifier
        </Button>
      </div>

      {resultat && (
        <div className="mt-4 space-y-3">
          {resultat.resultats.map((r) => (
            <div key={r.fournisseur}>
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium capitalize">{r.fournisseur}</span>
                {r.statut === "ok" && <StatusChip tone="ok">{r.n_servis} modèles servis</StatusChip>}
                {r.statut === "sans_cle" && <StatusChip tone="line2">aucune clé</StatusChip>}
                {r.statut === "injoignable" && <StatusChip tone="alert">injoignable</StatusChip>}
              </div>
              {r.detail && r.statut !== "ok" && (
                <p className="text-[11px] text-ink-soft mt-1 wrap-break-word">{r.detail}</p>
              )}
              <ul className="mt-1.5 space-y-1">
                {r.modeles.map((m) => (
                  <li key={m.modele} className="flex items-center gap-2 text-xs font-mono">
                    {m.servi
                      ? <Check size={13} className="text-ok shrink-0" />
                      : <AlertTriangle size={13} className="text-alert shrink-0" />}
                    <span className={m.servi ? "" : "text-alert"}>{m.modele}</span>
                    {!m.servi && <span className="text-ink-soft">— non servi</span>}
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {resultat.verdict === "MODELES_ABSENTS" ? (
            <div className="flex items-start gap-2 rounded-lg border border-alert/40 bg-alert/10 p-3 text-xs">
              <AlertTriangle size={14} className="text-alert mt-0.5 shrink-0" />
              <p>
                {resultat.modeles_absents.length} modèle(s) configuré(s) ne sont plus servis.
                L'assistant fonctionnera tant qu'un étage de la cascade répond, mais le repli
                annoncé n'existe pas. Préférer un alias — <span className="font-mono">gemini-flash-latest</span> —
                à une version figée, qui disparaît à chaque changement de génération.
              </p>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs text-ok">
              <Check size={14} /> Tous les modèles configurés répondent.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
