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


def _snapshot(metrics: dict, extra: dict | None = None) -> dict:
    """Extrait les mesures suivies d'un résultat de clustering."""
    extra = extra or {}
    snap = {k: metrics.get(k) for k in _SNAP_KEYS}
    snap["n_disperses_total"] = int(extra.get("n_disperses", 0)) + int(extra.get("n_non_affectes", 0))
    return snap


def _silhouette_gelee() -> float:
    """Silhouette du point de conception gelé (bootstrap de la référence). Défaut 0.4334."""
    try:
        with open(settings.quality_frozen_config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        return float(cfg["metriques_routieres"]["silhouette_routier"])
    except Exception:
        return 0.4334


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
            "silhouette": float(m.get("silhouette_routier")),
            "compacite_med_m": m.get("compacite_med_m"),
            "compacite_max_m": m.get("compacite_max_m"),
            "taille_max": m.get("taille_max"),
            "faisable": m.get("faisable", True),
            "n_disperses_total": int(cfg.get("n_disperses_individuel", 0)),
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
    mes = _snapshot(metrics, extra)
    raisons: list[str] = []
    niveau = "OK"

    plancher = round(settings.quality_sil_floor_rel * _silhouette_gelee(), 4)
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
        os.makedirs(os.path.dirname(settings.quality_baseline_path) or ".", exist_ok=True)
        with open(settings.quality_baseline_path, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)
        logger.info("[MS6] Baseline qualité mise à jour (silhouette=%s)", snap.get("silhouette"))
        return True
    except Exception as exc:
        logger.warning("[MS6] Écriture baseline qualité échouée : %s", exc)
        return False
