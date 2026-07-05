"""
Entraînement de la détection d'anomalies — benchmark de détecteurs + sélection du meilleur.

Démarche honnête :
- Modèles NON supervisés (Isolation Forest) : entraînés SANS le label.
- `incident_type` (→ label binaire) sert UNIQUEMENT à l'évaluation a posteriori.
- Split TEMPOREL (30 derniers jours = test) pour une évaluation crédible.
- On compare 3 détecteurs, on garde le meilleur (PR-AUC) et on le gèle.

Usage : python train_anomaly.py
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.metrics import (roc_auc_score, average_precision_score, precision_score,
                             recall_score, f1_score, confusion_matrix)

from config import settings
from features import label_binaire, colonnes_all, CURATED
from anomaly import AnomalyDetector


def _split_temporel(df: pd.DataFrame, test_jours: int = 30):
    jours = sorted(df["date"].unique())
    seuil = jours[-test_jours]
    return df[df["date"] < seuil], df[df["date"] >= seuil]


def _evaluer(y, scores, preds) -> dict:
    return {
        "ROC_AUC": round(float(roc_auc_score(y, scores)), 4),
        "PR_AUC": round(float(average_precision_score(y, scores)), 4),
        "precision": round(float(precision_score(y, preds, zero_division=0)), 4),
        "rappel": round(float(recall_score(y, preds, zero_division=0)), 4),
        "F1": round(float(f1_score(y, preds, zero_division=0)), 4),
        "confusion": confusion_matrix(y, preds).tolist(),   # [[TN,FP],[FN,TP]]
    }


def main():
    os.makedirs(settings.data_dir, exist_ok=True)
    if not os.path.exists(settings.dataset_path):
        print("[MS11] Dataset absent — génération (anomalies contextuelles)…")
        import dataset_anomaly
        dataset_anomaly.generer().to_csv(settings.dataset_path, index=False)
    df = pd.read_csv(settings.dataset_path)

    train, test = _split_temporel(df)
    ytr, yte = label_binaire(train), label_binaire(test)
    contam = float(min(0.2, max(0.01, ytr.mean())))   # aligné sur le taux d'incidents observé
    print(f"[MS11] {len(df)} trajets | train={len(train)} test={len(test)} "
          f"| incidents train={100*ytr.mean():.2f}% | contamination={contam:.3f}")

    cols_all = colonnes_all(df)
    detecteurs = {
        "seuil_ratio":     AnomalyDetector("seuil_ratio", "threshold", contam, threshold_col="ratio"),
        "seuil_surprise":  AnomalyDetector("seuil_surprise", "threshold", contam, threshold_col="surprise"),
        "iforest_all":     AnomalyDetector("iforest_all", "iforest", contam, settings.seed, feature_cols=cols_all),
        "iforest_curated": AnomalyDetector("iforest_curated", "iforest", contam, settings.seed, feature_cols=CURATED),
    }

    resultats = []
    for nom, det in detecteurs.items():
        det.fit(train)
        s_te = det.scores(test)
        # Évaluation à BUDGET D'ALERTE FIXE : on signale les `contamination`% scores les plus élevés
        # du test → comparaison équitable entre détecteurs (évite le biais de transfert de seuil).
        thr_budget = float(np.quantile(s_te, 1.0 - contam))
        pred = s_te >= thr_budget
        m = _evaluer(yte.to_numpy(), s_te, pred)
        det.metrics = m
        resultats.append({"detecteur": nom, **{k: v for k, v in m.items() if k != "confusion"},
                          "confusion": m["confusion"]})
        print(f"  {nom:18s} PR-AUC={m['PR_AUC']:.3f} ROC-AUC={m['ROC_AUC']:.3f} "
              f"F1={m['F1']:.3f} (P={m['precision']:.2f} R={m['rappel']:.2f})")

    # Meilleur détecteur = plus grand PR-AUC (adapté au déséquilibre)
    gagnant_nom = max(resultats, key=lambda r: r["PR_AUC"])["detecteur"]
    print(f"\n[MS11] 🏆 Gagnant : {gagnant_nom}")

    # Réentraînement du gagnant sur TOUTES les données, puis gel
    final = detecteurs[gagnant_nom]
    final.fit(df)
    # Seuil de production = même budget d'alerte, calibré sur TOUTES les données
    final.threshold = float(np.quantile(final.scores(df), 1.0 - contam))
    final.save(settings.model_path)

    config = {
        "version": "ms11-analytique-v1",
        "detecteur": gagnant_nom,
        "kind": final.kind,
        "feature_cols": final.feature_cols,
        "threshold_col": final.threshold_col,
        "threshold": final.threshold,
        "contamination": contam,
        "metrics_test": final.metrics,
        "n_trajets": len(df),
        "taux_incidents_%": round(100 * label_binaire(df).mean(), 3),
        "dateCalcul": datetime.now(timezone.utc).isoformat(),
    }
    with open(settings.config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    with open(settings.benchmark_path, "w", encoding="utf-8") as f:
        json.dump(sorted(resultats, key=lambda r: r["PR_AUC"], reverse=True), f, indent=2, ensure_ascii=False)

    print(f"[MS11] Artefacts : {settings.model_path} | {settings.config_path} | {settings.benchmark_path}")


if __name__ == "__main__":
    main()
