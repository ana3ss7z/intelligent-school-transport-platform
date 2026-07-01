"""
Catalogue des régresseurs candidats pour le benchmark ETA.

Chaque entrée renvoie un estimateur scikit-learn compatible `.fit()/.predict()`.
Les modèles sensibles à l'échelle (linéaires, KNN, SVR, MLP) sont enveloppés dans un
Pipeline(StandardScaler → modèle) ; les arbres/boosting n'en ont pas besoin.
"""
import logging

from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (RandomForestRegressor, ExtraTreesRegressor,
                              GradientBoostingRegressor, HistGradientBoostingRegressor)
from sklearn.linear_model import LinearRegression, Ridge, ElasticNet
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


def catalogue(seed: int = 42) -> dict:
    """Nom → estimateur. XGBoost/LightGBM ajoutés si les libs sont installées."""
    models: dict = {
        # Baseline statistique (référence basse)
        "baseline_moyenne": DummyRegressor(strategy="mean"),
        # Linéaires (avec normalisation)
        "linear": make_pipeline(StandardScaler(), LinearRegression()),
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0, random_state=seed)),
        "elasticnet": make_pipeline(StandardScaler(),
                                    ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=seed)),
        "knn": make_pipeline(StandardScaler(), KNeighborsRegressor(n_neighbors=15)),
        # Ensembles d'arbres (pas de scaling)
        "random_forest": RandomForestRegressor(n_estimators=300, n_jobs=-1, random_state=seed),
        "extra_trees": ExtraTreesRegressor(n_estimators=300, n_jobs=-1, random_state=seed),
        "gradient_boosting": GradientBoostingRegressor(random_state=seed),
        "hist_gb": HistGradientBoostingRegressor(random_state=seed),
    }

    try:
        from xgboost import XGBRegressor
        models["xgboost"] = XGBRegressor(
            n_estimators=400, max_depth=6, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9, n_jobs=-1, random_state=seed)
    except Exception as exc:  # pragma: no cover
        logger.warning("XGBoost indisponible : %s", exc)

    try:
        from lightgbm import LGBMRegressor
        models["lightgbm"] = LGBMRegressor(
            n_estimators=500, max_depth=-1, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9, n_jobs=-1, random_state=seed, verbose=-1)
    except Exception as exc:  # pragma: no cover
        logger.warning("LightGBM indisponible : %s", exc)

    return models


# Modèles « baseline » exclus du choix du gagnant (servent de référence)
BASELINES = {"baseline_moyenne", "baseline_osrm"}
