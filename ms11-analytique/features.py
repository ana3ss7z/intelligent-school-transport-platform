"""
Feature engineering pour la détection d'anomalies (trajets déjà OBSERVÉS).

Signaux construits (le feature engineering est ICI le vrai enjeu — plus que le choix du modèle) :
- `ratio`    = durée réelle / durée de base OSRM  → capte les gros retards « francs ».
- `surprise` = ratio / ratio ATTENDU vu le contexte (trafic/météo/ramadan/souk)
               → capte les **anomalies contextuelles** (ratio élevé alors que les conditions sont légères).
- `dwell`, `nb_montees`, `nb_descentes`, `taux_occupation` → captent les **anomalies de surcharge**
               (durée quasi normale mais activité d'arrêt anormale).

Aucune seule variable ne capte les 3 natures d'anomalie → d'où l'intérêt d'un détecteur **multivarié**
sur un jeu de features **curées**. `incident_type` reste un LABEL (évaluation seulement).
"""
import pandas as pd

METEO_CATS = ["ensoleille", "nuageux", "pluie", "brouillard"]
TRAFIC_CATS = ["fluide", "modere", "dense", "embouteillage"]
LABEL = "incident_type"

# Coefficients de congestion attendue (mêmes ordres de grandeur que le générateur)
FT = {"fluide": 1.00, "modere": 1.15, "dense": 1.40, "embouteillage": 1.80}
FM = {"ensoleille": 1.00, "nuageux": 1.03, "pluie": 1.20, "brouillard": 1.15}

# Sous-ensemble « curé » pour le détecteur multivarié (évite la dilution)
CURATED = ["surprise", "ratio", "dwell", "nb_montees", "nb_descentes", "taux_occupation"]


def label_binaire(df: pd.DataFrame) -> pd.Series:
    return (df[LABEL].astype(str) != "none").astype(int)


def _num(df, col, defaut=0.0):
    return pd.to_numeric(df.get(col, defaut), errors="coerce").fillna(defaut)


def build(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame brut (trajets observés) → matrice de features numériques."""
    out = pd.DataFrame(index=df.index)
    base_s = _num(df, "duree_base_s", 1.0).clip(lower=1.0)
    reel_s = _num(df, "duree_reelle_min", 0.0) * 60.0

    ratio = reel_s / base_s
    # Congestion ATTENDUE d'après le contexte
    meteo = df.get("meteo", "ensoleille").astype(str)
    trafic = df.get("trafic", "fluide").astype(str)
    exp = (trafic.map(FT).fillna(1.0) * meteo.map(FM).fillna(1.0)
           * (1.0 + 0.15 * _num(df, "ramadan", 0.0)) * (1.0 + 0.10 * _num(df, "jour_souk", 0.0)))

    out["ratio"] = ratio
    out["surprise"] = ratio / exp.clip(lower=0.5)          # >1 = pire que prévu vu le contexte
    out["ecart_min"] = (reel_s - base_s) / 60.0
    out["retard_cumule_s"] = _num(df, "retard_cumule_s", 0.0)
    out["duree_base_s"] = base_s
    out["distance_routiere_m"] = _num(df, "distance_routiere_m", 0.0)
    out["dwell"] = _num(df, "nb_montees", 0.0) + _num(df, "nb_descentes", 0.0)
    out["nb_montees"] = _num(df, "nb_montees", 0.0)
    out["nb_descentes"] = _num(df, "nb_descentes", 0.0)
    out["taux_occupation"] = _num(df, "taux_occupation", 0.0)
    out["nb_arrets_restants"] = _num(df, "nb_arrets_restants", 0.0)
    out["nb_feux"] = _num(df, "nb_feux", 0.0)
    for c in ("ramadan", "jour_souk", "travaux_prevus", "traverse_oued"):
        out[c] = _num(df, c, 0.0)
    out["is_soir"] = (df.get("moment", "matin").astype(str) == "soir").astype(int)
    for cat in METEO_CATS:
        out[f"meteo_{cat}"] = (meteo == cat).astype(int)
    for cat in TRAFIC_CATS:
        out[f"trafic_{cat}"] = (trafic == cat).astype(int)
    return out


def colonnes_all(df: pd.DataFrame) -> list[str]:
    return list(build(df.head(1)).columns)
