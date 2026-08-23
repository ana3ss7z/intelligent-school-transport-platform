"""
MS12 — évaluer ce que le service fait VRAIMENT, et vérifier que son gagnant en est un.

Cinq questions sans réponse dans le dossier
-------------------------------------------
1. **Le mode `facteur_contexte` n'a aucune métrique.** Le modèle est entraîné sur des tronçons de
   0,7–4 km ; en production les fronts demandent l'ETA d'une **tournée restante** de 6 à 12 km.
   `model.predire_minutes` bascule alors sur un mode de repli — et *c'est ce mode-là qui tourne*.
   Le docstring l'admet lui-même : « les métriques publiées (MAE 1,32 min) n'y valent plus rien ».
2. **Le gagnant tient à 2,7 secondes.** ElasticNet 1,3219 min contre Ridge 1,3668 : 0,045 min
   d'écart, sur 720 points dont 1 % d'incidents à ±100 minutes. Aucun intervalle de confiance.
3. **Une baseline évidente manque** : la moyenne historique par (circuit, moment, tronçon). Elle
   existe déjà comme *feature* ; elle n'a jamais été évaluée comme *prédicteur autonome*.
4. **Un biais résiduel de +0,55 min** est affiché dans le notebook 03 sans être commenté, alors que
   le MAE des trajets normaux vaut 0,859 : les deux tiers de l'erreur moyenne sont un décalage
   constant, donc corrigeable.
5. **Aucune ablation de features.** Les « importances » publiées sont des |coefficients| standardisés :
   elles disent ce que le modèle *utilise*, pas ce qu'il *perdrait* sans.

Contrainte absolue : **ne jamais écraser l'artefact gelé.** Tout ce qui est réentraîné ici reste en
mémoire ou va dans `data/ablation/`. `eta_model.pkl` et `eta_config.json` ne sont jamais écrits.

    python ablation.py      → rapport + data/ablation/resultats.json
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from algorithms import BASELINES, catalogue
from config import settings
from features import TARGET, preparer_features
from train import _split_temporel

SORTIE = os.path.join(settings.data_dir, "ablation")

# Familles de features — le regroupement qui a un sens métier, pas un regroupement syntaxique.
FAMILLES = {
    "temporel": ["heure_sin", "heure_cos", "jour_semaine", "mois", "is_soir"],
    "conditions": ["meteo_ensoleille", "meteo_nuageux", "meteo_pluie", "meteo_brouillard",
                   "trafic_fluide", "trafic_modere", "trafic_dense", "trafic_embouteillage"],
    "route": ["distance_routiere_m", "duree_base_s", "nb_feux", "traverse_oued"],
    "dwell": ["nb_montees", "nb_descentes", "taux_occupation", "nb_arrets_restants"],
    "contexte_marocain": ["ramadan", "jour_souk"],
    "travaux": ["travaux_prevus"],
    "historique": ["duree_moyenne_historique_s", "retard_cumule_s"],
}


def _metriques(y, p) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    return {"MAE": round(float(mean_absolute_error(y, p)), 4),
            "RMSE": round(float(np.sqrt(((y - p) ** 2).mean())), 4),
            "R2": round(float(r2_score(y, p)), 4),
            "MAPE_%": round(float((np.abs(y - p) / np.maximum(1e-6, y)).mean() * 100), 2),
            "biais": round(float((p - y).mean()), 4)}


def charger() -> pd.DataFrame:
    return pd.read_csv(settings.dataset_path)


# ══════════ 1. Le mode de production : `facteur_contexte` ═══════════════════
def trajets_complets(df: pd.DataFrame) -> pd.DataFrame:
    """Agrège les tronçons en TRAJETS ENTIERS — sans rien inventer.

    Un trajet est la concaténation de ses tronçons : sa distance est leur somme, sa durée réelle
    aussi. On obtient donc des observations de 6 à 12 km **produites par les mêmes lois** que
    l'entraînement, sans régénérer quoi que ce soit ni supposer une extrapolation des facteurs.
    C'est exactement le régime que le service rencontre en production.
    """
    cles = ["date", "moment", "circuit_id"]
    somme = {"distance_routiere_m": "sum", "duree_base_s": "sum", TARGET: "sum",
             "nb_montees": "sum", "nb_descentes": "sum", "duree_moyenne_historique_s": "sum"}
    premier = {"jour_semaine": "first", "mois": "first", "heure_depart": "first",
               "meteo": "first", "trafic": "first", "ramadan": "first", "jour_souk": "first",
               "travaux_prevus": "first", "traverse_oued": "first", "nb_feux": "first",
               "taux_occupation": "max", "retard_cumule_s": "first"}
    g = df.groupby(cles, as_index=False).agg({**somme, **premier})
    g["nb_arrets_restants"] = df.groupby(cles)["nb_arrets_restants"].max().to_numpy()
    # Un trajet est « anormal » dès qu'un seul de ses tronçons a subi un incident.
    inc = df.groupby(cles)["incident_type"].apply(lambda s: (s != "none").any()).to_numpy()
    g["incident"] = inc
    return g


def evaluer_garde(df: pd.DataFrame) -> dict:
    """Trois façons d'estimer la durée d'un trajet entier, sur la période de test."""
    from model import eta_model
    if not eta_model.load():
        raise SystemExit("Artefact gelé introuvable — lancer train.py d'abord.")

    _, test = _split_temporel(df)
    trajets = trajets_complets(test)
    normaux = trajets[~trajets["incident"]]

    lignes = {}
    for nom, sous in (("tous", trajets), ("normaux", normaux)):
        y = sous[TARGET].to_numpy()
        # (a) le modèle extrapolé directement, hors de son domaine
        direct = eta_model.predict_df(sous)
        # (b) OSRM brut : la baseline métier
        osrm = sous["duree_base_s"].to_numpy() / 60.0
        # (c) la garde réellement en production
        garde, modes = [], []
        for _, r in sous.iterrows():
            v, m = eta_model.predire_minutes(r.to_dict())
            garde.append(v)
            modes.append(m)
        lignes[nom] = {
            "n": len(sous),
            "modele_extrapole": _metriques(y, direct),
            "osrm_brut": _metriques(y, osrm),
            "facteur_contexte": _metriques(y, garde),
            "modes": pd.Series(modes).value_counts().to_dict(),
        }
    lignes["domaine"] = eta_model.domaine
    lignes["plage_trajets"] = {
        "distance_min_m": round(float(trajets["distance_routiere_m"].min()), 1),
        "distance_max_m": round(float(trajets["distance_routiere_m"].max()), 1),
    }
    return lignes


# ══════════ 2. Le gagnant est-il significativement meilleur ? ═══════════════
def significativite(df: pd.DataFrame, n_boot: int = 5000, seed: int = 42) -> dict:
    """Bootstrap APPARIÉ sur les erreurs absolues du test.

    Apparié : on rééchantillonne les **mêmes indices** pour les deux modèles, donc on compare leurs
    erreurs sur les mêmes trajets. C'est ce qui permet de conclure sur la *différence* plutôt que
    sur deux moyennes indépendantes.
    """
    train, test = _split_temporel(df)
    Xtr, ytr = preparer_features(train), train[TARGET].to_numpy()
    Xte, yte = preparer_features(test), test[TARGET].to_numpy()

    err = {}
    for nom, est in catalogue(settings.seed if hasattr(settings, "seed") else 42).items():
        if nom in BASELINES:
            continue
        try:
            est.fit(Xtr, ytr)
            err[nom] = np.abs(est.predict(Xte) - yte)
        except Exception as exc:                      # xgboost/lightgbm éventuellement absents
            print(f"    ({nom} ignoré : {exc})")
    err["baseline_osrm"] = np.abs(test["duree_base_s"].to_numpy() / 60.0 - yte)

    classement = sorted(err, key=lambda n: err[n].mean())
    champion = classement[0]
    rng = np.random.default_rng(seed)
    n = len(yte)
    idx = [rng.integers(0, n, n) for _ in range(n_boot)]

    out = {"champion": champion, "MAE": {k: round(float(v.mean()), 4) for k, v in err.items()},
           "comparaisons": {}}
    for nom in classement[1:]:
        d = err[nom] - err[champion]                  # > 0 ⇒ le champion est meilleur
        boots = np.array([d[i].mean() for i in idx])
        out["comparaisons"][nom] = {
            "delta_MAE": round(float(d.mean()), 4),
            "IC95_bas": round(float(np.percentile(boots, 2.5)), 4),
            "IC95_haut": round(float(np.percentile(boots, 97.5)), 4),
            "p_le_champion_est_meilleur": round(float((boots > 0).mean()), 4),
            "significatif_5%": bool(np.percentile(boots, 2.5) > 0),
        }
    return out


# ══════════ 3. La baseline manquante : la moyenne historique ════════════════
def baseline_historique(df: pd.DataFrame) -> dict:
    """« Ce qu'a duré ce tronçon les jours précédents » — sans aucun apprentissage.

    Cette baseline-là est le vrai plancher métier : elle ne demande qu'un tableur. Si le modèle ne
    la bat pas nettement, il ne mérite pas d'exister.
    """
    train, test = _split_temporel(df)
    cles = ["circuit_id", "moment", "leg_id"]
    ref = train.groupby(cles)[TARGET].mean()
    pred = test.set_index(cles).index.map(ref).to_numpy(dtype=float)
    globale = float(train[TARGET].mean())
    pred = np.where(np.isnan(pred), globale, pred)
    y = test[TARGET].to_numpy()
    masque = (test["incident_type"] == "none").to_numpy()
    return {"tous": _metriques(y, pred), "normaux": _metriques(y[masque], pred[masque])}


# ══════════ 4. Le biais résiduel : deux tiers de l'erreur ? ═════════════════
def biais_residuel(df: pd.DataFrame) -> dict:
    """Le modèle sur-prédit-il systématiquement ? Et que gagnerait une simple constante ?

    La correction est estimée **sur le train uniquement** : la calibrer sur le test serait
    évidemment tricher.
    """
    train, test = _split_temporel(df)
    est = catalogue(42)["elasticnet"]
    Xtr, ytr = preparer_features(train), train[TARGET].to_numpy()
    est.fit(Xtr, ytr)

    p_tr = est.predict(Xtr)
    normaux_tr = (train["incident_type"] == "none").to_numpy()
    correction = float((p_tr[normaux_tr] - ytr[normaux_tr]).mean())

    Xte, yte = preparer_features(test), test[TARGET].to_numpy()
    p_te = est.predict(Xte)
    normaux_te = (test["incident_type"] == "none").to_numpy()
    return {
        "correction_estimee_sur_train_min": round(correction, 4),
        "avant": {"tous": _metriques(yte, p_te),
                  "normaux": _metriques(yte[normaux_te], p_te[normaux_te])},
        "apres": {"tous": _metriques(yte, p_te - correction),
                  "normaux": _metriques(yte[normaux_te], p_te[normaux_te] - correction)},
    }


# ══════════ 5. Ablation par famille de features ═════════════════════════════
def ablation_familles(df: pd.DataFrame) -> list[dict]:
    """Que perd-on en retirant chaque famille ? (le modèle est réentraîné à chaque fois)"""
    train, test = _split_temporel(df)
    Xtr_full, Xte_full = preparer_features(train), preparer_features(test)
    ytr, yte = train[TARGET].to_numpy(), test[TARGET].to_numpy()
    normaux = (test["incident_type"] == "none").to_numpy()

    def score(cols: list[str]) -> tuple[float, float]:
        est = catalogue(42)["elasticnet"]
        est.fit(Xtr_full[cols], ytr)
        p = est.predict(Xte_full[cols])
        return (mean_absolute_error(yte, p),
                mean_absolute_error(yte[normaux], p[normaux]))

    toutes = list(Xtr_full.columns)
    mae_ref, mae_ref_n = score(toutes)
    lignes = [{"variante": "modele complet", "n_features": len(toutes),
               "MAE_tous": round(mae_ref, 4), "MAE_normaux": round(mae_ref_n, 4),
               "delta_normaux": 0.0}]
    for nom, cols in FAMILLES.items():
        restantes = [c for c in toutes if c not in cols]
        if not restantes:
            continue
        m, mn = score(restantes)
        lignes.append({"variante": f"sans {nom}", "n_features": len(restantes),
                       "MAE_tous": round(m, 4), "MAE_normaux": round(mn, 4),
                       "delta_normaux": round(mn - mae_ref_n, 4)})
    return lignes


# ══════════ 6. Les arbres perdent-ils parce qu'ils sont mal réglés ? ════════
def reglage_arbres(df: pd.DataFrame, n_iter: int = 25, seed: int = 42) -> dict:
    """Conclure « XGBoost perd » sur des arbres aux hyperparamètres par défaut n'est pas défendable.

    On donne donc un budget de recherche aux deux modèles à arbres les plus sérieux, avec une
    validation **temporelle** (`TimeSeriesSplit`) — jamais aléatoire, sinon on entraînerait sur le
    futur. Le linéaire, lui, n'a presque rien à régler : c'est un avantage structurel, pas un biais
    de protocole, et il faut le dire.
    """
    from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
    from sklearn.ensemble import RandomForestRegressor

    train, test = _split_temporel(df)
    Xtr, ytr = preparer_features(train), train[TARGET].to_numpy()
    Xte, yte = preparer_features(test), test[TARGET].to_numpy()
    cv = TimeSeriesSplit(n_splits=3)

    grilles = {}
    try:
        from xgboost import XGBRegressor
        grilles["xgboost"] = (XGBRegressor(random_state=seed, n_jobs=-1, verbosity=0), {
            "n_estimators": [200, 400, 800, 1500],
            "max_depth": [2, 3, 4, 6, 8],
            "learning_rate": [0.01, 0.03, 0.05, 0.1],
            "subsample": [0.7, 0.85, 1.0],
            "colsample_bytree": [0.6, 0.8, 1.0],
            "reg_lambda": [0.1, 1.0, 10.0],
            "min_child_weight": [1, 5, 20],
        })
    except ImportError:
        pass
    grilles["random_forest"] = (RandomForestRegressor(random_state=seed, n_jobs=-1), {
        "n_estimators": [200, 400, 800],
        "max_depth": [None, 6, 12, 20],
        "min_samples_leaf": [1, 3, 10, 25],
        "max_features": ["sqrt", 0.5, 1.0],
    })

    out = {}
    for nom, (est, grille) in grilles.items():
        rs = RandomizedSearchCV(est, grille, n_iter=n_iter, cv=cv,
                                scoring="neg_mean_absolute_error",
                                random_state=seed, n_jobs=1, refit=True)
        rs.fit(Xtr, ytr)
        p = rs.best_estimator_.predict(Xte)
        out[nom] = {"meilleurs_params": {k: (v if isinstance(v, (int, float, str)) else str(v))
                                         for k, v in rs.best_params_.items()},
                    "MAE_test": round(float(mean_absolute_error(yte, p)), 4)}
    est = catalogue(seed)["elasticnet"]
    est.fit(Xtr, ytr)
    out["elasticnet_reference"] = {
        "MAE_test": round(float(mean_absolute_error(yte, est.predict(Xte))), 4)}
    return out


def main() -> None:
    df = charger()
    train, test = _split_temporel(df)
    print(f"[MS12] {len(df)} lignes | train={len(train)} test={len(test)}\n")

    print("## 1. Le mode reellement execute en production : facteur_contexte\n")
    g = evaluer_garde(df)
    print(f"Trajets entiers de test : {g['tous']['n']} "
          f"({g['plage_trajets']['distance_min_m']:.0f}-{g['plage_trajets']['distance_max_m']:.0f} m) "
          f"| domaine d entrainement max = "
          f"{g['domaine']['distance_routiere_m']['max']:.0f} m\n")
    for vue in ("tous", "normaux"):
        print(f"**{vue}** (n={g[vue]['n']}, modes={g[vue]['modes']})\n")
        print("| Estimateur | MAE (min) | RMSE | R2 | MAPE | Biais |")
        print("|---|--:|--:|--:|--:|--:|")
        for nom in ("modele_extrapole", "osrm_brut", "facteur_contexte"):
            m = g[vue][nom]
            print(f"| {nom} | {m['MAE']:.3f} | {m['RMSE']:.3f} | {m['R2']:.3f} "
                  f"| {m['MAPE_%']:.1f} % | {m['biais']:+.3f} |")
        print()

    print("## 2. Le gagnant est-il significatif ? (bootstrap apparie, 5000 tirages)\n")
    s = significativite(df)
    print(f"Champion mesure : **{s['champion']}** (MAE {s['MAE'][s['champion']]:.4f})\n")
    print("| Challenger | MAE | delta MAE | IC 95 % de la difference | Significatif a 5 % |")
    print("|---|--:|--:|---|:-:|")
    for nom, c in s["comparaisons"].items():
        print(f"| {nom} | {s['MAE'][nom]:.4f} | {c['delta_MAE']:+.4f} "
              f"| [{c['IC95_bas']:+.4f} ; {c['IC95_haut']:+.4f}] "
              f"| {'OUI' if c['significatif_5%'] else 'non'} |")

    print("\n## 3. La baseline manquante : moyenne historique par (circuit, moment, troncon)\n")
    b = baseline_historique(df)
    print("| Vue | MAE | RMSE | R2 |")
    print("|---|--:|--:|--:|")
    for vue in ("tous", "normaux"):
        m = b[vue]
        print(f"| {vue} | {m['MAE']:.4f} | {m['RMSE']:.4f} | {m['R2']:.4f} |")

    print("\n## 4. Biais residuel\n")
    bi = biais_residuel(df)
    print(f"Correction constante estimee sur le TRAIN : {bi['correction_estimee_sur_train_min']:+.3f} min\n")
    print("| Vue | MAE avant | MAE apres | Biais avant | Biais apres |")
    print("|---|--:|--:|--:|--:|")
    for vue in ("tous", "normaux"):
        a, ap = bi["avant"][vue], bi["apres"][vue]
        print(f"| {vue} | {a['MAE']:.4f} | {ap['MAE']:.4f} | {a['biais']:+.4f} | {ap['biais']:+.4f} |")

    print("\n## 5. Ablation par famille de features\n")
    ab = ablation_familles(df)
    print("| Variante | Features | MAE tous | MAE normaux | Perte (normaux) |")
    print("|---|--:|--:|--:|--:|")
    for l in ab:
        print(f"| {l['variante']} | {l['n_features']} | {l['MAE_tous']:.4f} "
              f"| {l['MAE_normaux']:.4f} | {l['delta_normaux']:+.4f} |")

    print("\n## 6. Et si on reglait les arbres ? (RandomizedSearchCV, validation temporelle)\n")
    rg = reglage_arbres(df)
    print("| Modele | MAE test |")
    print("|---|--:|")
    for nom, d in rg.items():
        print(f"| {nom} | {d['MAE_test']:.4f} |")
    for nom, d in rg.items():
        if "meilleurs_params" in d:
            print(f"\n`{nom}` : {d['meilleurs_params']}")

    os.makedirs(SORTIE, exist_ok=True)
    with open(os.path.join(SORTIE, "resultats.json"), "w", encoding="utf-8") as f:
        json.dump({"garde": g, "significativite": s, "baseline_historique": b,
                   "biais": bi, "ablation_familles": ab, "reglage_arbres": rg},
                  f, indent=2, ensure_ascii=False)
    print(f"\n[MS12] -> {os.path.join(SORTIE, 'resultats.json')}")
    print("[MS12] Artefacts geles NON modifies (eta_model.pkl, eta_config.json).")


if __name__ == "__main__":
    main()
