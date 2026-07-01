"""
Chargement & prédiction du MEILLEUR modèle (agnostique du type de modèle).

Le service ne connaît pas l'algorithme gagnant : il charge `eta_model.pkl` + `eta_config.json`
(qui contient l'ordre des colonnes de features) et applique la même transformation qu'à l'entraînement.
"""
from __future__ import annotations
import json
import os

import joblib
import pandas as pd

from config import settings
from features import preparer_features


class ETAModel:
    def __init__(self):
        self.model = None
        self.config: dict = {}
        self.feature_columns: list[str] = []

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def load(self) -> bool:
        if not (os.path.exists(settings.model_path) and os.path.exists(settings.config_path)):
            return False
        self.model = joblib.load(settings.model_path)
        with open(settings.config_path, encoding="utf-8") as f:
            self.config = json.load(f)
        self.feature_columns = self.config.get("feature_columns", [])
        return True

    def predict_df(self, df_brut: pd.DataFrame):
        """DataFrame brut (colonnes attendues par features.preparer_features) → durées prédites (min)."""
        if not self.loaded:
            raise RuntimeError("Modèle non chargé — lancer train.py d'abord.")
        X = preparer_features(df_brut)
        X = X.reindex(columns=self.feature_columns, fill_value=0)  # ordre stable, colonnes manquantes = 0
        return self.model.predict(X)


# Instance unique partagée par le service
eta_model = ETAModel()
