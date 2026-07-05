"""
Détecteur d'anomalies — wrapper unifié (agnostique) persistable via joblib.

Deux familles, même interface (score croissant = plus anormal ; `predict` = score ≥ seuil) :
- kind="threshold" : seuil sur UNE colonne (ex. `ratio` ou `surprise`) — baselines univariées.
- kind="iforest"   : IsolationForest sur un jeu de colonnes CURÉES (multivarié).
"""
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest

import features as feat


class AnomalyDetector:
    def __init__(self, name: str, kind: str, contamination: float, seed: int = 42,
                 feature_cols: list[str] | None = None, threshold_col: str | None = None):
        self.name = name
        self.kind = kind                    # "threshold" | "iforest"
        self.contamination = contamination
        self.seed = seed
        self.feature_cols = feature_cols or []
        self.threshold_col = threshold_col
        self.model = None
        self.threshold: float | None = None
        self.metrics: dict = {}

    def fit(self, df):
        F = feat.build(df)
        if self.kind == "threshold":
            s = F[self.threshold_col].to_numpy()
        else:
            X = F[self.feature_cols]
            self.model = IsolationForest(n_estimators=300, contamination=self.contamination,
                                         random_state=self.seed, n_jobs=-1).fit(X)
            s = -self.model.score_samples(X)
        self.threshold = float(np.quantile(s, 1.0 - self.contamination))
        return self

    def scores(self, df) -> np.ndarray:
        F = feat.build(df)
        if self.kind == "threshold":
            return F[self.threshold_col].to_numpy()
        X = F.reindex(columns=self.feature_cols, fill_value=0.0)
        return -self.model.score_samples(X)

    def predict(self, df) -> np.ndarray:
        return self.scores(df) >= self.threshold

    def save(self, path):
        joblib.dump(self, path)

    @staticmethod
    def load(path) -> "AnomalyDetector":
        return joblib.load(path)
