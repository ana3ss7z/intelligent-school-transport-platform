"""
Pipeline d'entraînement ETA — benchmark multi-modèles + sélection honnête du gagnant.

Étapes :
1. Charge le dataset (le génère si absent).
2. Split TEMPOREL (les N derniers jours d'école = test) → pas de fuite temporelle.
3. Entraîne TOUS les régresseurs du catalogue + une baseline métier (durée OSRM brute).
4. Évalue MAE / RMSE / R² / MAPE, en double vue (tous trajets vs trajets normaux sans incident).
5. Choisit le meilleur (MAE test le plus bas, hors baselines), le réentraîne sur toutes les données,
   puis gèle l'artefact (eta_model.pkl) + la config (eta_config.json) + le comparatif (benchmark_summary.json).

Usage : `python train.py`
"""
from __future__ import annotations
import json
import os
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (mean_absolute_error, mean_squared_error, r2_score,
                             mean_absolute_percentage_error)

from config import settings
from features import preparer_features, liste_features, TARGET, LABEL
from algorithms import catalogue, BASELINES
import dataset as dataset_mod


def _charger_dataset() -> pd.DataFrame:
    if not os.path.exists(settings.dataset_path):
        print("[MS12] Dataset absent — génération…")
        os.makedirs(settings.data_dir, exist_ok=True)
        dataset_mod.generer().to_csv(settings.dataset_path, index=False)
    return pd.read_csv(settings.dataset_path)


def _split_temporel(df: pd.DataFrame):
    jours = sorted(df["date"].unique())
    seuil = jours[-settings.test_jours]
    train = df[df["date"] < seuil]
    test = df[df["date"] >= seuil]
    return train, test


def _metriques(y_true, y_pred) -> dict:
    return {
        "MAE": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "RMSE": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "R2": round(float(r2_score(y_true, y_pred)), 4),
        "MAPE_%": round(float(mean_absolute_percentage_error(y_true, y_pred) * 100), 2),
    }


def evaluer(y_true, y_pred, mask_normal) -> dict:
    """Double vue : tous les trajets + trajets normaux (hors incidents)."""
    res = {"tous": _metriques(y_true, y_pred)}
    if mask_normal.any():
        res["normaux"] = _metriques(y_true[mask_normal], y_pred[mask_normal])
    return res


def main():
    os.makedirs(settings.data_dir, exist_ok=True)
    df = _charger_dataset()
    feat_cols = liste_features(df)

    train, test = _split_temporel(df)
    Xtr, ytr = preparer_features(train)[feat_cols], train[TARGET].to_numpy()
    Xte, yte = preparer_features(test)[feat_cols], test[TARGET].to_numpy()
    mask_normal = (test[LABEL].to_numpy() == "none")

    print(f"[MS12] {len(df)} lignes | train={len(train)} test={len(test)} "
          f"| {len(feat_cols)} features | incidents test={100*(~mask_normal).mean():.1f}%")

    resultats = []

    # Baseline métier : durée OSRM brute (aucun apprentissage)
    base_pred = test["duree_base_s"].to_numpy() / 60.0
    resultats.append({"modele": "baseline_osrm", "baseline": True, "fit_s": 0.0,
                      **{f"test_{k}": v for k, v in _metriques(yte, base_pred).items()},
                      "eval": evaluer(yte, base_pred, mask_normal)})

    # Tous les régresseurs du catalogue
    modeles = catalogue(seed=settings.seed)
    fitted = {}
    for nom, est in modeles.items():
        t0 = time.perf_counter()
        est.fit(Xtr, ytr)
        fit_s = round(time.perf_counter() - t0, 3)
        pred = est.predict(Xte)
        fitted[nom] = est
        resultats.append({"modele": nom, "baseline": nom in BASELINES, "fit_s": fit_s,
                          **{f"test_{k}": v for k, v in _metriques(yte, pred).items()},
                          "eval": evaluer(yte, pred, mask_normal)})
        print(f"  {nom:20s} MAE={resultats[-1]['test_MAE']:6.3f} min "
              f"R2={resultats[-1]['test_R2']:.3f} ({fit_s}s)")

    # Choix du gagnant : plus petit MAE test parmi les modèles NON-baseline
    candidats = [r for r in resultats if not r["baseline"]]
    gagnant = min(candidats, key=lambda r: r["test_MAE"])
    nom_gagnant = gagnant["modele"]
    base_mae = next(r for r in resultats if r["modele"] == "baseline_osrm")["test_MAE"]
    gain_pct = round(100 * (base_mae - gagnant["test_MAE"]) / base_mae, 1)
    print(f"\n[MS12] 🏆 Gagnant : {nom_gagnant} — MAE={gagnant['test_MAE']} min "
          f"(baseline OSRM {base_mae} → gain {gain_pct}%)")

    # Réentraînement du gagnant sur TOUTES les données puis gel
    X_all, y_all = preparer_features(df)[feat_cols], df[TARGET].to_numpy()
    final = catalogue(seed=settings.seed)[nom_gagnant]
    final.fit(X_all, y_all)
    joblib.dump(final, settings.model_path)

    # Importance des features (si dispo)
    importances = _importances(final, feat_cols)

    config = {
        "version": "ms12-prediction-v1",
        "algorithme": nom_gagnant,
        "params": {k: str(v) for k, v in _params(final).items()},
        "feature_columns": feat_cols,
        "cible": TARGET,
        "metrics_test": gagnant["eval"],
        "baseline_osrm_test": next(r["eval"] for r in resultats if r["modele"] == "baseline_osrm"),
        "gain_vs_baseline_%": gain_pct,
        "mae_minutes": gagnant["test_MAE"],
        "n_lignes": len(df),
        "n_features": len(feat_cols),
        "importances": importances,
        "dateCalcul": datetime.now(timezone.utc).isoformat(),
    }
    with open(settings.config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    with open(settings.benchmark_path, "w", encoding="utf-8") as f:
        json.dump(sorted(resultats, key=lambda r: r["test_MAE"]), f, indent=2, ensure_ascii=False)

    print(f"[MS12] Artefacts : {settings.model_path} | {settings.config_path} | {settings.benchmark_path}")


def _params(est) -> dict:
    try:
        return est.get_params(deep=False)
    except Exception:
        return {}


def _importances(est, feat_cols) -> dict:
    """Importance des features : `feature_importances_` (arbres) ou |coef_| (linéaires standardisés)."""
    model = est.steps[-1][1] if hasattr(est, "steps") else est
    imp = getattr(model, "feature_importances_", None)
    if imp is None:
        coef = getattr(model, "coef_", None)
        if coef is None:
            return {}
        imp = np.abs(np.ravel(coef))            # linéaire : |coefficient| sur features standardisées
    pairs = sorted(zip(feat_cols, [float(x) for x in imp]), key=lambda t: t[1], reverse=True)
    return {k: round(v, 4) for k, v in pairs[:15]}


if __name__ == "__main__":
    main()
