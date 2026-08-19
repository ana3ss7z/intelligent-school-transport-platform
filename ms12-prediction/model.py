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
        self.domaine: dict = {}

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
        self.domaine = self.config.get("domaine_entrainement") or self._domaine_depuis_dataset()
        return True

    @staticmethod
    def _domaine_depuis_dataset() -> dict:
        """
        Bornes de validité, relues du dataset si le config gelé est antérieur à leur ajout.

        Le modèle a été entraîné sur des TRONÇONS entre deux arrêts (~0,7–4 km). Les appelants
        peuvent lui soumettre une tournée restante bien plus longue : il faut connaître la limite
        pour ne pas extrapoler en silence.
        """
        try:
            df = pd.read_csv(settings.dataset_path, usecols=["distance_routiere_m", "duree_base_s"])
            return {
                "distance_routiere_m": {"min": float(df["distance_routiere_m"].min()),
                                        "max": float(df["distance_routiere_m"].max()),
                                        "median": float(df["distance_routiere_m"].median())},
                "duree_base_s": {"min": float(df["duree_base_s"].min()),
                                 "max": float(df["duree_base_s"].max()),
                                 "median": float(df["duree_base_s"].median())},
            }
        except Exception:
            return {}

    def predict_df(self, df_brut: pd.DataFrame):
        """DataFrame brut (colonnes attendues par features.preparer_features) → durées prédites (min)."""
        if not self.loaded:
            raise RuntimeError("Modèle non chargé — lancer train.py d'abord.")
        X = preparer_features(df_brut)
        X = X.reindex(columns=self.feature_columns, fill_value=0)  # ordre stable, colonnes manquantes = 0
        return self.model.predict(X)

    def predire_minutes(self, row: dict) -> tuple[float, str]:
        """
        ETA en minutes + mode de calcul employé.

        Le modèle a été entraîné sur des **tronçons** (0,7–4 km). Depuis que les fronts demandent
        l'ETA de la **tournée restante** (jusqu'à ~12 km : la boucle école→élèves→école), l'entrée
        peut sortir du domaine d'apprentissage — et les métriques publiées (MAE 1,32 min) n'y valent
        plus rien.

        Plutôt que d'extrapoler en silence, on **garde le modèle dans son domaine** :
        on l'interroge sur un tronçon de RÉFÉRENCE (la médiane d'entraînement) avec **le contexte
        réel du moment** (heure, météo, trafic, ramadan, souk, travaux, dwell). Le rapport
        `eta_référence / durée_libre_référence` est le **facteur d'inflation contextuel** — ce que
        le modèle sait vraiment estimer — qu'on applique à la durée OSRM restante.

        En clair : le ML fournit le *combien ça se dégrade aujourd'hui*, OSRM fournit *la distance*.
        """
        dist = float(row.get("distance_routiere_m") or 0.0)
        dur = float(row.get("duree_base_s") or 0.0)
        dist_max = (self.domaine.get("distance_routiere_m") or {}).get("max")
        dur_max = (self.domaine.get("duree_base_s") or {}).get("max")

        hors_domaine = (dist_max is not None and dist > dist_max) or (dur_max is not None and dur > dur_max)
        if not hors_domaine or dur <= 0:
            return float(self.predict_df(pd.DataFrame([row]))[0]), "modele_direct"

        dist_ref = (self.domaine.get("distance_routiere_m") or {}).get("median", dist_max)
        dur_ref = (self.domaine.get("duree_base_s") or {}).get("median", dur_max)
        row_ref = {**row, "distance_routiere_m": dist_ref, "duree_base_s": dur_ref,
                   "duree_moyenne_historique_s": dur_ref}
        eta_ref_min = float(self.predict_df(pd.DataFrame([row_ref]))[0])

        facteur = eta_ref_min / (dur_ref / 60.0)
        return facteur * (dur / 60.0), "facteur_contexte"


# Instance unique partagée par le service
eta_model = ETAModel()
