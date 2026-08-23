"""
Ce que le benchmark gelé de MS11 ne dit pas — trois mesures manquantes.

`train_anomaly.py` compare quatre détecteurs, choisit `iforest_curated` (PR-AUC 0,9127) et gèle
l'artefact. Le protocole est propre : split temporel, budget d'alerte égalisé, label jamais vu à
l'entraînement. Mais trois questions qu'un jury posera n'ont pas de réponse dans le dossier.

1. **La fuite générateur → feature.** `features.FT` / `features.FM` reprennent **exactement** les
   coefficients `F_TRAFIC` / `F_METEO` de `dataset_anomaly.py`. La variable `surprise`, qui est
   l'argument central du service, connaît donc le processus qui a fabriqué les données. Sur le
   terrain, personne ne connaît ces coefficients : il faudrait les **estimer**. Combien perd-on ?

2. **Le rappel par nature d'anomalie.** Toute la thèse du service est que « le seuil univarié
   attrape les francs mais rate le contextuel et la surcharge ». Ce chiffre n'existe nulle part —
   on n'a que le rappel global.

3. **L'incertitude.** Le test contient **8 positifs**. Une seule anomalie qui bascule déplace le
   rappel de 12,5 points, et pourtant les métriques sont publiées avec quatre décimales.

    python ablation_anomaly.py     → rapport + data/ablation_anomaly.json
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score

import features as feat
from anomaly import AnomalyDetector
from config import settings
from features import CURATED, colonnes_all, label_binaire
from train_anomaly import _split_temporel

# Regroupe les libellés d'incident en NATURES, telles que le générateur les produit.
NATURES = {
    "panne": "franc", "accident": "franc", "route_bloquee": "franc",
    "retard_contextuel": "contextuel",
    "surcharge": "surcharge",
}


def _detecteurs(df: pd.DataFrame, contam: float) -> dict[str, AnomalyDetector]:
    """Les quatre détecteurs du benchmark gelé, reconstruits à l'identique."""
    cols = colonnes_all(df)
    return {
        "seuil_ratio": AnomalyDetector("seuil_ratio", "threshold", contam, threshold_col="ratio"),
        "seuil_surprise": AnomalyDetector("seuil_surprise", "threshold", contam, threshold_col="surprise"),
        "iforest_all": AnomalyDetector("iforest_all", "iforest", contam, settings.seed, feature_cols=cols),
        "iforest_curated": AnomalyDetector("iforest_curated", "iforest", contam, settings.seed,
                                           feature_cols=CURATED),
    }


def _budget(scores: np.ndarray, part: float) -> np.ndarray:
    """Prédiction à budget d'alerte fixe — le protocole du benchmark gelé."""
    return scores >= float(np.quantile(scores, 1.0 - part))


# ═══════════════ 1. Quantifier la fuite générateur → feature ═════════════════
def estimer_coefficients(train: pd.DataFrame) -> tuple[dict, dict]:
    """Estime les facteurs de congestion **depuis les données**, sans regarder le générateur.

    Méthode : médiane stratifiée du log-ratio. Pour le trafic, on ne regarde que les jours de
    météo neutre (`ensoleille`) afin de ne pas confondre les deux effets ; symétriquement pour la
    météo à trafic `fluide`. La médiane est choisie plutôt que la moyenne parce que 1,25 % des
    lignes sont précisément des anomalies : une moyenne les absorberait dans l'estimation.

    C'est exactement ce que ferait un exploitant qui dispose de son historique et de rien d'autre.
    """
    ratio = (pd.to_numeric(train["duree_reelle_min"]) * 60.0
             / pd.to_numeric(train["duree_base_s"]).clip(lower=1.0))
    log_r = np.log(ratio.clip(lower=1e-6))

    ft, fm = {}, {}
    base_t = log_r[(train["meteo"] == "ensoleille")]
    ref_t = float(np.median(base_t[train["trafic"] == "fluide"]))
    for cat in feat.TRAFIC_CATS:
        sel = base_t[train["trafic"] == cat]
        ft[cat] = float(np.exp(np.median(sel) - ref_t)) if len(sel) >= 20 else 1.0

    base_m = log_r[(train["trafic"] == "fluide")]
    ref_m = float(np.median(base_m[train["meteo"] == "ensoleille"]))
    for cat in feat.METEO_CATS:
        sel = base_m[train["meteo"] == cat]
        fm[cat] = float(np.exp(np.median(sel) - ref_m)) if len(sel) >= 20 else 1.0
    return ft, fm


def ablation_fuite(df: pd.DataFrame, contam: float) -> dict:
    train, test = _split_temporel(df)
    yte = label_binaire(test).to_numpy()

    ft_est, fm_est = estimer_coefficients(train)
    ft_ref, fm_ref = dict(feat.FT), dict(feat.FM)

    resultats = {}
    for variante, (ft, fm) in (("code_en_dur", (ft_ref, fm_ref)),
                               ("estime_des_donnees", (ft_est, fm_est))):
        feat.FT, feat.FM = ft, fm      # `build()` lit ces globales à chaque appel
        try:
            ligne = {}
            for nom, det in _detecteurs(df, contam).items():
                det.fit(train)
                s = det.scores(test)
                pred = _budget(s, contam)
                ligne[nom] = {
                    "PR_AUC": round(float(average_precision_score(yte, s)), 4),
                    "ROC_AUC": round(float(roc_auc_score(yte, s)), 4),
                    "precision": round(float(precision_score(yte, pred, zero_division=0)), 4),
                    "rappel": round(float(recall_score(yte, pred, zero_division=0)), 4),
                }
            resultats[variante] = ligne
        finally:
            feat.FT, feat.FM = ft_ref, fm_ref
    return {
        "coefficients_generateur": {"trafic": ft_ref, "meteo": fm_ref},
        "coefficients_estimes": {"trafic": {k: round(v, 3) for k, v in ft_est.items()},
                                 "meteo": {k: round(v, 3) for k, v in fm_est.items()}},
        "resultats": resultats,
    }


# ═══════════════════ 2. Rappel par nature d'anomalie ════════════════════════
def rappel_par_nature(df: pd.DataFrame, contam: float) -> dict:
    train, test = _split_temporel(df)
    natures = test["incident_type"].map(NATURES).fillna("none")
    yte = label_binaire(test).to_numpy()

    out = {"effectifs": natures[natures != "none"].value_counts().to_dict(), "detecteurs": {}}
    for nom, det in _detecteurs(df, contam).items():
        det.fit(train)
        pred = _budget(det.scores(test), contam)
        par_nature = {}
        for nature in ("franc", "contextuel", "surcharge"):
            masque = (natures == nature).to_numpy()
            n = int(masque.sum())
            par_nature[nature] = {
                "n": n,
                "detectes": int(pred[masque].sum()),
                "rappel": round(float(pred[masque].mean()), 3) if n else None,
            }
        par_nature["global"] = {"n": int(yte.sum()), "detectes": int(pred[yte == 1].sum()),
                                "rappel": round(float(pred[yte == 1].mean()), 3)}
        out["detecteurs"][nom] = par_nature
    return out


# ═════════════ 3. Incertitude : bootstrap + budget d'alerte ═════════════════
def incertitude(df: pd.DataFrame, contam: float, n_boot: int = 2000, seed: int = 42) -> dict:
    train, test = _split_temporel(df)
    yte = label_binaire(test).to_numpy()
    rng = np.random.default_rng(seed)

    scores = {}
    for nom, det in _detecteurs(df, contam).items():
        det.fit(train)
        scores[nom] = det.scores(test)

    out = {"n_test": len(yte), "n_positifs": int(yte.sum()), "n_boot": n_boot, "detecteurs": {}}
    n = len(yte)
    idx_boot = [rng.integers(0, n, n) for _ in range(n_boot)]
    for nom, s in scores.items():
        vals = []
        for idx in idx_boot:
            y_b = yte[idx]
            if y_b.sum() == 0 or y_b.sum() == len(y_b):
                continue          # un rééchantillon sans aucun positif n'a pas de PR-AUC
            vals.append(average_precision_score(y_b, s[idx]))
        vals = np.array(vals)
        out["detecteurs"][nom] = {
            "PR_AUC_point": round(float(average_precision_score(yte, s)), 4),
            "IC95_bas": round(float(np.percentile(vals, 2.5)), 4),
            "IC95_haut": round(float(np.percentile(vals, 97.5)), 4),
            "ecart_type": round(float(vals.std()), 4),
            "n_rééchantillons_valides": int(len(vals)),
        }
    return out


def balayage_budget(df: pd.DataFrame, budgets=(0.005, 0.01, 0.0128, 0.02, 0.03, 0.05, 0.10)) -> list[dict]:
    """« Et si je tolère plus d'alertes par jour ? » — la question de l'exploitant."""
    train, test = _split_temporel(df)
    yte = label_binaire(test).to_numpy()
    contam = float(min(0.2, max(0.01, label_binaire(train).mean())))

    scores = {}
    for nom, det in _detecteurs(df, contam).items():
        det.fit(train)
        scores[nom] = det.scores(test)

    lignes = []
    for b in budgets:
        ligne = {"budget_%": round(100 * b, 2), "alertes": int(round(b * len(yte)))}
        for nom, s in scores.items():
            pred = _budget(s, b)
            ligne[f"{nom}_P"] = round(float(precision_score(yte, pred, zero_division=0)), 3)
            ligne[f"{nom}_R"] = round(float(recall_score(yte, pred, zero_division=0)), 3)
        lignes.append(ligne)
    return lignes


# ═══════ 4. Validation temporelle glissante — pour avoir assez de positifs ═══
def validation_glissante(df: pd.DataFrame, n_folds: int = 6, test_jours: int = 30,
                         coeffs_estimes: bool = False) -> dict:
    """Origine glissante : `n_folds` blocs de test successifs, entraînement sur le passé seulement.

    Motivation directe : le split unique du benchmark gelé ne laisse que **8 positifs** dans le
    test, dont **un seul** de nature « contextuelle ». Aucune affirmation par nature d'anomalie
    n'est soutenable sur un tel effectif — ni dans un sens, ni dans l'autre. En agrégeant six
    blocs on évalue l'équivalent de six mois de test, et on obtient enfin des effectifs qui
    permettent de trancher.
    """
    jours = sorted(df["date"].unique())
    contam_ref = float(min(0.2, max(0.01, label_binaire(df).mean())))
    noms = list(_detecteurs(df.head(50), contam_ref))
    agrege = {n: {"y": [], "pred": [], "nature": [], "pr_auc_par_fold": []} for n in noms}

    for k in range(n_folds):
        fin = len(jours) - k * test_jours
        debut = fin - test_jours
        if debut <= test_jours:                     # il faut de quoi entraîner
            break
        j_test = set(jours[debut:fin])
        train = df[df["date"].isin(set(jours[:debut]))]
        test = df[df["date"].isin(j_test)]
        ytr, yte = label_binaire(train), label_binaire(test)
        if yte.sum() == 0:
            continue
        contam = float(min(0.2, max(0.01, ytr.mean())))
        natures = test["incident_type"].map(NATURES).fillna("none")

        # Variante « sans connaissance privilégiée » : les coefficients de congestion sont
        # ré-estimés sur le train DE CE BLOC — jamais sur le test, jamais depuis le générateur.
        ref = (dict(feat.FT), dict(feat.FM))
        if coeffs_estimes:
            feat.FT, feat.FM = estimer_coefficients(train)
        try:
            for nom, det in _detecteurs(df, contam).items():
                det.fit(train)
                s = det.scores(test)
                pred = _budget(s, contam)
                a = agrege[nom]
                a["y"].extend(yte.tolist())
                a["pred"].extend(pred.tolist())
                a["nature"].extend(natures.tolist())
                a["pr_auc_par_fold"].append(round(float(average_precision_score(yte, s)), 4))
        finally:
            feat.FT, feat.FM = ref

    out = {"n_folds_utilises": len(agrege[noms[0]]["pr_auc_par_fold"]), "detecteurs": {}}
    for nom, a in agrege.items():
        y = np.array(a["y"]); pred = np.array(a["pred"]); nat = np.array(a["nature"])
        par_nature = {}
        for nature in ("franc", "contextuel", "surcharge"):
            m = nat == nature
            par_nature[nature] = {"n": int(m.sum()), "detectes": int(pred[m].sum()),
                                  "rappel": round(float(pred[m].mean()), 3) if m.sum() else None}
        folds = np.array(a["pr_auc_par_fold"])
        out["detecteurs"][nom] = {
            "PR_AUC_moyen": round(float(folds.mean()), 4),
            "PR_AUC_ecart_type": round(float(folds.std()), 4),
            "PR_AUC_par_fold": a["pr_auc_par_fold"],
            "precision_agregee": round(float(precision_score(y, pred, zero_division=0)), 3),
            "rappel_agrege": round(float(recall_score(y, pred, zero_division=0)), 3),
            "n_positifs_total": int(y.sum()),
            "par_nature": par_nature,
        }
    return out


def _union_a_cible(s_a: np.ndarray, s_b: np.ndarray, cible: int) -> np.ndarray:
    """Union de deux détecteurs calibrée pour émettre ≈ `cible` alertes au total.

    Recherche dichotomique sur le budget accordé à chacun. Sans cette calibration, l'union
    comparerait deux volumes d'alerte différents — la faute que tout le protocole cherche à éviter.
    """
    lo, hi = 0.0, 1.0
    meilleur = np.zeros(len(s_a), dtype=bool)
    for _ in range(40):
        mid = (lo + hi) / 2
        u = _budget(s_a, mid) | _budget(s_b, mid)
        n = int(u.sum())
        meilleur = u
        if n > cible:
            hi = mid
        elif n < cible:
            lo = mid
        else:
            break
    return meilleur


# ═════════ 6. L'union des deux gagnants, à budget d'alerte ÉGAL ═════════════
def combinaison(df: pd.DataFrame, n_folds: int = 6, test_jours: int = 30) -> dict:
    """`seuil_surprise` et `iforest_curated` ne ratent pas les mêmes anomalies. Et si on les unissait ?

    La règle du protocole s'applique ici aussi : une union qui alerte deux fois plus n'aurait aucun
    mérite. On donne donc à chaque détecteur **la moitié** du budget, pour que le total d'alertes
    reste celui d'un détecteur seul. C'est la seule comparaison honnête.
    """
    jours = sorted(df["date"].unique())
    agrege = {c: {"y": [], "pred": [], "nature": []}
              for c in ("seuil_surprise", "iforest_curated", "union_budget_egal")}

    for k in range(n_folds):
        fin = len(jours) - k * test_jours
        debut = fin - test_jours
        if debut <= test_jours:
            break
        train = df[df["date"].isin(set(jours[:debut]))]
        test = df[df["date"].isin(set(jours[debut:fin]))]
        ytr, yte = label_binaire(train), label_binaire(test)
        if yte.sum() == 0:
            continue
        contam = float(min(0.2, max(0.01, ytr.mean())))
        natures = test["incident_type"].map(NATURES).fillna("none")

        dets = _detecteurs(df, contam)
        s = {}
        for nom in ("seuil_surprise", "iforest_curated"):
            dets[nom].fit(train)
            s[nom] = dets[nom].scores(test)

        # Budget de référence : le nombre d'alertes qu'émet UN détecteur seul sur ce bloc.
        cible = int(_budget(s["seuil_surprise"], contam).sum())
        preds = {
            "seuil_surprise": _budget(s["seuil_surprise"], contam),
            "iforest_curated": _budget(s["iforest_curated"], contam),
            # Les deux détecteurs se recouvrent beaucoup en tête de classement : leur donner
            # `contam/2` chacun produit BIEN MOINS d'alertes que la cible, donc moins de budget,
            # donc une comparaison injuste. On cherche le budget par détecteur qui ramène l'union
            # au même nombre d'alertes qu'un détecteur seul.
            "union_budget_egal": _union_a_cible(s["seuil_surprise"], s["iforest_curated"], cible),
        }
        for nom, p in preds.items():
            agrege[nom]["y"].extend(yte.tolist())
            agrege[nom]["pred"].extend(p.tolist())
            agrege[nom]["nature"].extend(natures.tolist())

    out = {}
    for nom, a in agrege.items():
        y = np.array(a["y"]); pred = np.array(a["pred"]); nat = np.array(a["nature"])
        par_nature = {}
        for nature in ("franc", "contextuel", "surcharge"):
            m = nat == nature
            par_nature[nature] = {"n": int(m.sum()), "detectes": int(pred[m].sum())}
        out[nom] = {
            "alertes_emises": int(pred.sum()),
            "precision": round(float(precision_score(y, pred, zero_division=0)), 3),
            "rappel": round(float(recall_score(y, pred, zero_division=0)), 3),
            "par_nature": par_nature,
        }
    return out


def main() -> None:
    df = pd.read_csv(settings.dataset_path)
    train, test = _split_temporel(df)
    contam = float(min(0.2, max(0.01, label_binaire(train).mean())))
    print(f"[MS11] {len(df)} trajets | train={len(train)} test={len(test)} "
          f"| positifs test={int(label_binaire(test).sum())} | contamination={contam:.4f}\n")

    fuite = ablation_fuite(df, contam)
    print("## 1. Fuite generateur -> feature (coefficients de congestion)\n")
    print("| Categorie | Generateur (code en dur) | Estime des donnees |")
    print("|---|--:|--:|")
    for cat in feat.TRAFIC_CATS:
        print(f"| trafic {cat} | {fuite['coefficients_generateur']['trafic'][cat]:.2f} "
              f"| {fuite['coefficients_estimes']['trafic'][cat]:.2f} |")
    for cat in feat.METEO_CATS:
        print(f"| meteo {cat} | {fuite['coefficients_generateur']['meteo'][cat]:.2f} "
              f"| {fuite['coefficients_estimes']['meteo'][cat]:.2f} |")
    print("\n| Detecteur | PR-AUC (code en dur) | PR-AUC (estime) | Ecart |")
    print("|---|--:|--:|--:|")
    for nom in fuite["resultats"]["code_en_dur"]:
        a = fuite["resultats"]["code_en_dur"][nom]["PR_AUC"]
        b = fuite["resultats"]["estime_des_donnees"][nom]["PR_AUC"]
        print(f"| {nom} | {a:.4f} | {b:.4f} | {b - a:+.4f} |")

    nat = rappel_par_nature(df, contam)
    print(f"\n## 2. Rappel par nature d'anomalie (test : {nat['effectifs']})\n")
    print("| Detecteur | franc | contextuel | surcharge | global |")
    print("|---|--:|--:|--:|--:|")
    for nom, d in nat["detecteurs"].items():
        def c(k):
            v = d[k]
            return f"{v['detectes']}/{v['n']}" if v["n"] else "-"
        print(f"| {nom} | {c('franc')} | {c('contextuel')} | {c('surcharge')} | {c('global')} |")

    inc = incertitude(df, contam)
    print(f"\n## 3. Incertitude sur PR-AUC ({inc['n_positifs']} positifs, "
          f"bootstrap {inc['n_boot']})\n")
    print("| Detecteur | PR-AUC | IC 95 % | Ecart-type |")
    print("|---|--:|---|--:|")
    for nom, d in inc["detecteurs"].items():
        print(f"| {nom} | {d['PR_AUC_point']:.4f} | [{d['IC95_bas']:.3f} ; {d['IC95_haut']:.3f}] "
              f"| {d['ecart_type']:.3f} |")

    bud = balayage_budget(df)
    print("\n## 4. Budget d'alerte (precision / rappel)\n")
    noms = list(inc["detecteurs"])
    print("| Budget | Alertes | " + " | ".join(noms) + " |")
    print("|--:|--:|" + "---|" * len(noms))
    for l in bud:
        cells = [f"{l[f'{n}_P']:.2f} / {l[f'{n}_R']:.2f}" for n in noms]
        print(f"| {l['budget_%']} % | {l['alertes']} | " + " | ".join(cells) + " |")

    vg = validation_glissante(df)
    print(f"\n## 5. Validation temporelle glissante ({vg['n_folds_utilises']} blocs de 30 jours)\n")
    print("| Detecteur | PR-AUC moyen | Ecart-type | P | R | franc | contextuel | surcharge |")
    print("|---|--:|--:|--:|--:|--:|--:|--:|")
    for nom, d in vg["detecteurs"].items():
        pn = d["par_nature"]
        def c(k):
            v = pn[k]
            return f"{v['detectes']}/{v['n']}" if v["n"] else "-"
        print(f"| {nom} | {d['PR_AUC_moyen']:.3f} | {d['PR_AUC_ecart_type']:.3f} "
              f"| {d['precision_agregee']:.2f} | {d['rappel_agrege']:.2f} "
              f"| {c('franc')} | {c('contextuel')} | {c('surcharge')} |")
    print(f"\nPositifs agreges sur l'ensemble des blocs : "
          f"{vg['detecteurs'][list(vg['detecteurs'])[0]]['n_positifs_total']} "
          f"(contre 8 pour le split unique du benchmark gele).")

    vg_est = validation_glissante(df, coeffs_estimes=True)
    print("\n### Meme validation, coefficients de congestion ESTIMES par bloc "
          "(aucune connaissance du generateur)\n")
    print("| Detecteur | PR-AUC (code en dur) | PR-AUC (estime) | Ecart |")
    print("|---|--:|--:|--:|")
    for nom in vg["detecteurs"]:
        a = vg["detecteurs"][nom]["PR_AUC_moyen"]
        b = vg_est["detecteurs"][nom]["PR_AUC_moyen"]
        print(f"| {nom} | {a:.3f} | {b:.3f} | {b - a:+.3f} |")

    comb = combinaison(df)
    print("\n## 6. Union des deux gagnants, a budget d'alerte EGAL\n")
    print("| Detecteur | Alertes | P | R | franc | contextuel | surcharge |")
    print("|---|--:|--:|--:|--:|--:|--:|")
    for nom, d in comb.items():
        pn = d["par_nature"]
        def c(k):
            return f"{pn[k]['detectes']}/{pn[k]['n']}" if pn[k]["n"] else "-"
        print(f"| {nom} | {d['alertes_emises']} | {d['precision']:.2f} | {d['rappel']:.2f} "
              f"| {c('franc')} | {c('contextuel')} | {c('surcharge')} |")

    os.makedirs(settings.data_dir, exist_ok=True)
    chemin = os.path.join(settings.data_dir, "ablation_anomaly.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump({"fuite": fuite, "rappel_par_nature": nat, "incertitude": inc,
                   "budget": bud, "validation_glissante": vg,
                   "validation_glissante_coeffs_estimes": vg_est, "combinaison": comb},
                  f, indent=2, ensure_ascii=False)
    print(f"\n[MS11] -> {chemin}")


if __name__ == "__main__":
    main()
