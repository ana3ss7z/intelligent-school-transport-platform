"""
Garde-fou qualité du clustering — DYNAMIQUE et calibré sur notre point de fonctionnement réel.

Pourquoi pas un seuil fixe `silhouette < 0.5` : notre silhouette de production est ~0.43, un arbitrage
capacité↔compacité assumé (cf. notebooks/production_config.json). Un seuil 0.5 serait donc toujours au rouge.

Principe :
- signal PRIMAIRE = contrainte dure (faisabilité capacité) — respectable, binaire, indépendant du score ;
- référence DYNAMIQUE = nos propres runs acceptés (démarre à 0.43, s'auto-ajuste) ;
- alerte RELATIVE = régression vs la référence ; + un PLANCHER absolu ancré sur le point de conception
  (0.75 × silhouette_gelée ≈ 0.325), jamais 0.5, pour borner une dérive lente.

Le verdict est INFORMATIF (exposé via l'API + logs, pour le dashboard admin), pas un déclencheur de recalcul.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from config import settings

logger = logging.getLogger(__name__)

# Champs de métriques suivis dans la baseline
_SNAP_KEYS = ("silhouette", "compacite_med_m", "compacite_max_m", "taille_max", "faisable")

# Conditions dans lesquelles une référence a été prise. Deux d'entre elles la rendent
# INAPPLICABLE si elles changent (voir `reference_applicable`) : comparer la qualité obtenue avec
# des bus de 50 places à celle obtenue avec des bus de 60 n'a aucun sens.
_CONTEXTE_KEYS = ("n_eleves", "capacity", "rayon_max_m")


def _contexte(extra: dict | None) -> dict:
    extra = extra or {}
    return {
        "n_eleves": int(extra.get("n_eleves") or 0),
        "capacity": int(extra.get("capacity") or 0),
        "rayon_max_m": float(extra.get("rayon_max_m") or 0.0),
    }


def _snapshot(metrics: dict, extra: dict | None = None) -> dict:
    """Extrait les mesures suivies d'un résultat de clustering, **avec son contexte**.

    Le contexte n'est pas décoratif. Une référence écrite le 17/07 sur un jeu à 14 dispersés a
    servi cinq semaines à juger des runs à 17 dispersés — deux situations différentes comparées
    l'une à l'autre. Sans trace des conditions, rien ne permettait de s'en apercevoir.
    """
    extra = extra or {}
    snap = {k: metrics.get(k) for k in _SNAP_KEYS}
    snap["n_disperses_total"] = int(extra.get("n_disperses", 0)) + int(extra.get("n_non_affectes", 0))
    snap.update(_contexte(extra))
    return snap


def _silhouette_gelee() -> float:
    """Silhouette du point de conception gelé — l'**ancre** du garde-fou.

    On préfère `silhouette_partition_complete` quand elle existe : c'est la silhouette de la
    partition **finale** (tous les élèves), donc **la même grandeur** que celle qu'un run publie.
    L'historique `silhouette_routier` vaut 0,43336 mais porte sur les seuls élèves du **cœur**
    (283 sur 300, hors dispersés) — comparer l'une à l'autre revient à comparer deux mesures
    différentes. L'écart est aujourd'hui faible (1,8 %), donc inoffensif ; il ne le resterait pas.
    """
    try:
        with open(settings.quality_frozen_config_path, encoding="utf-8") as f:
            m = json.load(f)["metriques_routieres"]
        return float(m.get("silhouette_partition_complete") or m["silhouette_routier"])
    except Exception:
        return 0.4334


def reference_applicable(baseline: dict | None, extra: dict | None) -> dict | None:
    """Retourne la référence si elle a été prise dans des conditions comparables, sinon `None`.

    Deux changements la rendent inapplicable : la **capacité des bus** et le **rayon maximal**.
    Ce sont des paramètres structurels — ils redéfinissent le problème, pas seulement ses données.
    Le nombre d'élèves, lui, bouge naturellement au fil des inscriptions : on l'enregistre pour la
    traçabilité, mais on ne s'en sert pas pour invalider (sinon la référence ne servirait jamais).
    """
    if not baseline:
        return None
    ctx = _contexte(extra)
    ref_cap, ref_rayon = baseline.get("capacity"), baseline.get("rayon_max_m")
    if ref_cap is None and ref_rayon is None:
        return baseline                       # référence d'avant l'enregistrement du contexte
    if ref_cap is not None and int(ref_cap) != ctx["capacity"]:
        logger.info("[MS6] Référence qualité ignorée : capacité %s → %s", ref_cap, ctx["capacity"])
        return None
    if ref_rayon is not None and abs(float(ref_rayon) - ctx["rayon_max_m"]) > 1e-9:
        logger.info("[MS6] Référence qualité ignorée : rayon %s → %s", ref_rayon, ctx["rayon_max_m"])
        return None
    return baseline


def charger_baseline() -> dict | None:
    """Baseline persistée ; si absente, bootstrap depuis la config gelée (silhouette ~0.43, PAS 0.5)."""
    try:
        with open(settings.quality_baseline_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        pass
    # Bootstrap depuis production_config.json
    try:
        with open(settings.quality_frozen_config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        m = cfg["metriques_routieres"]
        return {
            "silhouette": float(m.get("silhouette_partition_complete") or m.get("silhouette_routier")),
            "compacite_med_m": m.get("compacite_med_m"),
            "compacite_max_m": m.get("compacite_max_m"),
            "taille_max": m.get("taille_max"),
            "faisable": m.get("faisable", True),
            "n_disperses_total": int(cfg.get("n_disperses_individuel", 0)),
            # Contexte du point de conception, pour que la référence sache d'où elle vient.
            "n_eleves": int(cfg.get("n_eleves", 0)),
            "capacity": int(cfg.get("capacite_bus", 0)),
            "rayon_max_m": float(cfg.get("rayon_max_m", 0.0)),
            "source": "bootstrap:production_config.json",
            "dateMAJ": None,
        }
    except Exception as exc:
        logger.warning("[MS6] Pas de baseline qualité (ni fichier ni config gelée) : %s", exc)
        return None


def evaluer_qualite(metrics: dict, extra: dict | None = None, baseline: dict | None = None) -> dict:
    """
    Verdict qualité : niveau ∈ {OK, DEGRADE, CRITIQUE} + raisons. Compare aux mesures de référence
    (relatif) et à un plancher absolu ancré sur le point de conception.
    """
    if baseline is None:
        baseline = charger_baseline()
    reference_brute = baseline                          # gardée pour distinguer « absente » de « écartée »
    baseline = reference_applicable(baseline, extra)     # ignorée si conditions non comparables
    mes = _snapshot(metrics, extra)
    raisons: list[str] = []
    niveau = "OK"

    ancre = _silhouette_gelee()
    plancher = round(settings.quality_sil_floor_rel * ancre, 4)
    sil = metrics.get("silhouette")

    # 1) Contrainte dure : capacité respectée ?
    if not metrics.get("faisable", False):
        niveau = "CRITIQUE"
        raisons.append(f"capacité dépassée (taille_max={metrics.get('taille_max')} > capacité)")

    # 2) Plancher absolu de silhouette (anti-effondrement lent)
    if sil is not None and sil < plancher:
        niveau = "CRITIQUE"
        raisons.append(f"silhouette {sil} < plancher {plancher} (0.75× point de conception)")

    # 3) Régression relative vs baseline (n'écrase pas un CRITIQUE)
    deltas: dict = {}
    if baseline:
        b_sil = baseline.get("silhouette")
        # ── Plafond : la référence ne peut jamais dépasser l'ancre ────────────
        # Sans lui, un run exceptionnellement bon fixe une référence que plus aucun run n'atteint.
        # Et comme la référence n'est réécrite QUE sur un verdict OK, le service se retrouve
        # bloqué : trop haute → DEGRADE → jamais mise à jour → toujours trop haute. C'est
        # exactement ce qui s'est produit du 17/07 au 24/08 — cinq semaines de DEGRADE permanent,
        # avec une référence à 0,5183 pour un niveau réellement atteignable de 0,4334.
        # La référence peut descendre (la détection de dérive continue de fonctionner) mais jamais
        # monter au-dessus de ce qu'on a documenté comme atteignable.
        if b_sil is not None and ancre and b_sil > ancre:
            logger.info("[MS6] Référence qualité plafonnée : %.4f → %.4f (point de conception)",
                        b_sil, ancre)
            b_sil = ancre
        if sil is not None and b_sil:
            drop_abs = round(b_sil - sil, 4)
            drop_rel = round(drop_abs / b_sil, 4) if b_sil else 0.0
            deltas["silhouette"] = {"baseline": b_sil, "actuel": sil, "chute_abs": drop_abs, "chute_rel": drop_rel}
            if drop_rel >= settings.quality_sil_drop_rel and drop_abs >= settings.quality_sil_drop_abs:
                raisons.append(f"silhouette −{drop_rel:.0%} vs référence ({b_sil}→{sil})")
                if niveau == "OK":
                    niveau = "DEGRADE"

        b_cmax = baseline.get("compacite_max_m")
        c_cmax = metrics.get("compacite_max_m")
        if b_cmax and c_cmax:
            inc_rel = round((c_cmax - b_cmax) / b_cmax, 4)
            deltas["compacite_max_m"] = {"baseline": b_cmax, "actuel": c_cmax, "hausse_rel": inc_rel}
            if inc_rel >= settings.quality_comp_inc_rel:
                raisons.append(f"compacité max +{inc_rel:.0%} vs référence ({b_cmax}→{c_cmax} m)")
                if niveau == "OK":
                    niveau = "DEGRADE"

        b_disp = baseline.get("n_disperses_total", 0) or 0
        c_disp = mes["n_disperses_total"]
        deltas["disperses"] = {"baseline": b_disp, "actuel": c_disp, "hausse": c_disp - b_disp}
        if c_disp - b_disp >= settings.quality_disperses_inc:
            raisons.append(f"dispersés +{c_disp - b_disp} vs référence ({b_disp}→{c_disp})")
            if niveau == "OK":
                niveau = "DEGRADE"
    elif reference_brute:
        # Distinction utile à l'exploitant : la référence existe, mais elle décrit une autre
        # situation. Dire « aucune référence » ici laisserait croire à une première évaluation.
        raisons.append("référence écartée — conditions différentes (capacité ou rayon max)")
    else:
        raisons.append("aucune référence — première évaluation (baseline à établir)")

    return {
        "niveau": niveau,
        "ok": niveau == "OK",
        "raisons": raisons,
        "mesures": mes,
        "baseline": baseline,
        "deltas": deltas,
        "plancher_silhouette": plancher,
        "seuils": {
            "sil_drop_rel": settings.quality_sil_drop_rel,
            "sil_drop_abs": settings.quality_sil_drop_abs,
            "comp_inc_rel": settings.quality_comp_inc_rel,
            "disperses_inc": settings.quality_disperses_inc,
        },
    }


def maybe_maj_baseline(metrics: dict, extra: dict | None, verdict: dict) -> bool:
    """Met à jour la référence (roulante) UNIQUEMENT si le run est OK. Retourne True si écrit."""
    if verdict.get("niveau") != "OK":
        return False
    snap = _snapshot(metrics, extra)
    snap["source"] = "run-applique"
    snap["dateMAJ"] = datetime.now(timezone.utc).isoformat()
    try:
        # Écriture atomique : deux calculs peuvent tourner en parallèle (endpoint HTTP et consumer
        # RabbitMQ). Un `open(..., "w")` interrompu laisserait ici un JSON tronqué, que le service
        # relirait au démarrage suivant comme référence de qualité.
        from etat import ecrire_json_atomique
        ecrire_json_atomique(settings.quality_baseline_path, snap)
        logger.info("[MS6] Baseline qualité mise à jour (silhouette=%s)", snap.get("silhouette"))
        return True
    except Exception as exc:
        logger.warning("[MS6] Écriture baseline qualité échouée : %s", exc)
        return False
