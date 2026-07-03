"""
Feature engineering pour la détection d'anomalies (trajets déjà OBSERVÉS).

Différence clé avec la prédiction ETA : ici on connaît la durée RÉELLE du trajet, donc on peut construire
le signal le plus révélateur d'un incident : le **ratio = durée réelle / durée de base OSRM**
(un trajet 5× plus long que prévu = très anormal). Ce signal est **auto-suffisant** : il ne dépend pas
du modèle ETA de MS12.

`incident_type` n'est JAMAIS une feature — c'est la vérité terrain pour l'évaluation (label binaire).
"""
import pandas as pd

METEO_CATS = ["ensoleille", "nuageux", "pluie", "brouillard"]
TRAFIC_CATS = ["fluide", "modere", "dense", "embouteillage"]
LABEL = "incident_type"


def label_binaire(df: pd.DataFrame) -> pd.Series:
    """1 = incident (anomalie réelle), 0 = trajet normal."""
    return (df[LABEL].astype(str) != "none").astype(int)


def _num(df, col, defaut=0.0):
    return pd.to_numeric(df.get(col, defaut), errors="coerce").fillna(defaut)


def build(df: pd.DataFrame, with_outcome: bool = True) -> pd.DataFrame:
    """
    Construit la matrice de features.
    with_outcome=True  → inclut le résultat observé (ratio, écart, retard cumulé) = détecteur fort.
    with_outcome=False → contexte AVANT trajet seulement = détecteur « aveugle » (baseline faible).
    """
    out = pd.DataFrame(index=df.index)
    base_s = _num(df, "duree_base_s", 1.0).clip(lower=1.0)

    if with_outcome:
        reel_s = _num(df, "duree_reelle_min", 0.0) * 60.0
        out["ratio"] = reel_s / base_s                     # signal clé
        out["ecart_min"] = (reel_s - base_s) / 60.0
        out["retard_cumule_s"] = _num(df, "retard_cumule_s", 0.0)

    # Contexte (connu au départ)
    out["duree_base_s"] = base_s
    out["distance_routiere_m"] = _num(df, "distance_routiere_m", 0.0)
    out["dwell"] = _num(df, "nb_montees", 0.0) + _num(df, "nb_descentes", 0.0)
    out["taux_occupation"] = _num(df, "taux_occupation", 0.0)
    out["nb_arrets_restants"] = _num(df, "nb_arrets_restants", 0.0)
    out["nb_feux"] = _num(df, "nb_feux", 0.0)
    for c in ("ramadan", "jour_souk", "travaux_prevus", "traverse_oued"):
        out[c] = _num(df, c, 0.0)
    out["is_soir"] = (df.get("moment", "matin").astype(str) == "soir").astype(int)

    meteo = df.get("meteo", "ensoleille").astype(str)
    for cat in METEO_CATS:
        out[f"meteo_{cat}"] = (meteo == cat).astype(int)
    trafic = df.get("trafic", "fluide").astype(str)
    for cat in TRAFIC_CATS:
        out[f"trafic_{cat}"] = (trafic == cat).astype(int)

    return out.reindex(sorted(out.columns), axis=1)


def liste_features(df: pd.DataFrame, with_outcome: bool = True) -> list[str]:
    return list(build(df.head(1), with_outcome).columns)
