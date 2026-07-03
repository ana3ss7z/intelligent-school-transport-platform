"""
Détecteur d'anomalies — wrapper unifié (agnostique) persistable via joblib.

Deux approches, même interface :
- "iforest" : IsolationForest (non supervisé) sur une matrice de features (avec ou sans le résultat observé) ;
- "ratio"   : baseline = seuil sur le ratio durée_réelle/durée_base.

Le score d'anomalie est croissant (plus haut = plus anormal). `predict` applique le seuil calibré
sur la proportion attendue d'anomalies (contamination).
"""
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest

import features as feat


class AnomalyDetector:
    def __init__(self, approach: str, contamination: float, seed: int = 42, with_outcome: bool = True):
        self.approach = approach            # "iforest" | "ratio"
        self.contamination = contamination
        self.seed = seed
        self.with_outcome = with_outcome
        self.model = None
        self.feature_columns: list[str] = []
        self.threshold: float | None = None
        self.metrics: dict = {}

    # ── entraînement ────────────────────────────────────────────────
    def fit(self, df):
        if self.approach == "ratio":
            self.feature_columns = ["ratio"]
            s = feat.build(df, with_outcome=True)["ratio"].to_numpy()
            self.threshold = float(np.quantile(s, 1.0 - self.contamination))
        else:
            X = feat.build(df, with_outcome=self.with_outcome)
            self.feature_columns = list(X.columns)
            self.model = IsolationForest(n_estimators=300, contamination=self.contamination,
                                         random_state=self.seed, n_jobs=-1)
            self.model.fit(X)
            # Frontière interne d'IsolationForest (cohérente avec sa contamination) :
            # anomalie ⇔ score_samples < offset_ ⇔ (-score_samples) > (-offset_).
            self.threshold = float(-self.model.offset_)
        return self

    # ── inférence ───────────────────────────────────────────────────
    def scores(self, df) -> np.ndarray:
        """Score d'anomalie (plus haut = plus anormal)."""
        if self.approach == "ratio":
            return feat.build(df, with_outcome=True)["ratio"].to_numpy()
        X = feat.build(df, with_outcome=self.with_outcome).reindex(
            columns=self.feature_columns, fill_value=0.0)
        return -self.model.score_samples(X)

    def predict(self, df) -> np.ndarray:
        """True = anomalie (score au-dessus du seuil)."""
        return self.scores(df) >= self.threshold

    # ── persistance ─────────────────────────────────────────────────
    def save(self, path):
        joblib.dump(self, path)

    @staticmethod
    def load(path) -> "AnomalyDetector":
        return joblib.load(path)
