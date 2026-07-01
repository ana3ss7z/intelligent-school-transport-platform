"""
Feature engineering ETA — partagé par dataset / train / service.

Principe (simple à comprendre) : on transforme le DataFrame brut (une ligne = un tronçon de trajet)
en une matrice **numérique** utilisable par tous les régresseurs (linéaires, forêts, boosting) :
- l'heure devient cyclique (sin/cos) pour que 23h soit proche de 0h ;
- les catégories météo/trafic deviennent des colonnes 0/1 (one-hot) → équitable pour les modèles linéaires ;
- les binaires (ramadan, souk, travaux, oued, service du soir) restent en 0/1 ;
- le reste passe en numérique brut.

IMPORTANT : `incident_type` n'est JAMAIS une feature (imprévisible à l'heure de départ) — c'est un label.
"""
import numpy as np
import pandas as pd

# Catégories fixes → colonnes one-hot stables entre entraînement et service
METEO_CATS = ["ensoleille", "nuageux", "pluie", "brouillard"]
TRAFIC_CATS = ["fluide", "modere", "dense", "embouteillage"]

# Colonnes numériques passées telles quelles
NUM_COLS = [
    "jour_semaine", "mois",
    "distance_routiere_m", "duree_base_s",
    "nb_arrets_restants", "nb_montees", "nb_descentes", "taux_occupation",
    "nb_feux", "duree_moyenne_historique_s", "retard_cumule_s",
]
# Colonnes binaires 0/1
BIN_COLS = ["is_soir", "ramadan", "jour_souk", "travaux_prevus", "traverse_oued"]

TARGET = "duree_reelle_min"
LABEL = "incident_type"


def preparer_features(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame brut -> matrice numérique de features (ordre de colonnes déterministe)."""
    out = pd.DataFrame(index=df.index)

    # Heure cyclique (période 24h)
    heure = df["heure_depart"].astype(float)
    out["heure_sin"] = np.sin(2 * np.pi * heure / 24.0)
    out["heure_cos"] = np.cos(2 * np.pi * heure / 24.0)

    # Service du soir (matin=0 / soir=1)
    out["is_soir"] = (df["moment"].astype(str) == "soir").astype(int)

    # Numériques
    for c in NUM_COLS:
        out[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # Binaires restants
    for c in BIN_COLS:
        if c == "is_soir":
            continue
        out[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    # One-hot météo / trafic (catégories fixes)
    meteo = df["meteo"].astype(str)
    for cat in METEO_CATS:
        out[f"meteo_{cat}"] = (meteo == cat).astype(int)
    trafic = df["trafic"].astype(str)
    for cat in TRAFIC_CATS:
        out[f"trafic_{cat}"] = (trafic == cat).astype(int)

    return out.reindex(sorted(out.columns), axis=1)


def liste_features(df: pd.DataFrame) -> list[str]:
    """Ordre canonique des colonnes de features (persisté dans eta_config.json)."""
    return list(preparer_features(df.head(1)).columns)
