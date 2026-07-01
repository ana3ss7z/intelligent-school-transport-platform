"""
Génère les 3 notebooks CRISP-DM de MS12 (via nbformat).
Chaque cellule de code est précédée d'une cellule markdown explicative ("approche simple à comprendre"),
même standard que les notebooks MS6.

Usage : python notebooks/build_notebooks.py   (puis exécution via nbconvert)
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))


def md(s):
    return nbf.v4.new_markdown_cell(s.strip("\n"))


def code(s):
    return nbf.v4.new_code_cell(s.strip("\n"))


SETUP = r'''
import os, sys, json, warnings
warnings.filterwarnings("ignore")
# Se placer à la racine du service (ms12-prediction) quel que soit le dossier d'exécution
while os.path.basename(os.getcwd()) == "notebooks":
    os.chdir("..")
sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd
import matplotlib.pyplot as plt, seaborn as sns
sns.set_theme(style="whitegrid", palette="deep")
os.makedirs("notebooks/figures", exist_ok=True)
from config import settings
print("Répertoire de travail :", os.getcwd())
'''

FIG = 'notebooks/figures'


# ══════════════════════════════════════════════════════════════════════
# NOTEBOOK 01 — Data study (EDA + prétraitement)
# ══════════════════════════════════════════════════════════════════════
def notebook_01():
    nb = nbf.v4.new_notebook()
    c = []
    c.append(md(r'''
# MS12 — Prédiction ETA · Notebook 01 : Étude des données (CRISP-DM)

**Objectif métier (Business Understanding).** Prédire la **durée réelle** d'un tronçon de trajet de bus
scolaire à Meknès (en minutes), afin d'informer parents et administration de l'heure d'arrivée estimée.

**Démarche.** On suit CRISP-DM : compréhension métier → compréhension des données (ce notebook) →
préparation → modélisation (notebook 02) → évaluation & déploiement (notebook 03).

**Nature des données.** Dataset **semi-réel** : la durée de base de chaque tronçon vient des **vraies routes
OSRM de Meknès** ; les facteurs (trafic, météo, Ramadan, souk, travaux) et les incidents sont simulés à
partir de coefficients de la littérature transport. On vise un **R² honnête (~0.75–0.85)** sur les trajets
normaux — pas un score parfait qui trahirait une fuite de données.
'''))
    c.append(md("**Étape 0 — Environnement.** On importe les librairies et on se place à la racine du service."))
    c.append(code(SETUP))

    c.append(md("**Étape 1 — Chargement.** On lit le dataset généré par `dataset.py` (une ligne = un tronçon de trajet un jour donné)."))
    c.append(code(r'''
import dataset as dataset_mod
if not os.path.exists(settings.dataset_path):
    print("Dataset absent — génération (nécessite OSRM, sinon repli vol d'oiseau)…")
    dataset_mod.generer().to_csv(settings.dataset_path, index=False)
df = pd.read_csv(settings.dataset_path)
print("Dimensions :", df.shape)
df.head()
'''))

    c.append(md("**Étape 2 — Qualité des données.** Types, valeurs manquantes et statistiques descriptives."))
    c.append(code(r'''
print("Valeurs manquantes :", int(df.isna().sum().sum()))
print("Jours :", df["date"].nunique(), "| Circuits :", df["circuit_id"].nunique())
df.describe(include="all").T.head(25)
'''))

    c.append(md(r'''
**Étape 3 — Distribution de la cible.** On regarde `duree_reelle_min`. La distribution est **à queue lourde** :
la grande majorité des trajets sont courts, mais quelques **incidents** (panne, accident…) créent des retards
extrêmes. C'est voulu et réaliste — et ces extrêmes seront des anomalies non prédictibles.
'''))
    c.append(code(r'''
fig, ax = plt.subplots(1, 2, figsize=(13, 4))
ax[0].hist(df["duree_reelle_min"], bins=80, color="#4c72b0")
ax[0].set_title("Distribution complète (queue lourde = incidents)"); ax[0].set_xlabel("minutes")
zoom = df[df["duree_reelle_min"] < 20]
ax[1].hist(zoom["duree_reelle_min"], bins=50, color="#55a868")
ax[1].set_title("Zoom trajets normaux (< 20 min)"); ax[1].set_xlabel("minutes")
plt.tight_layout(); plt.savefig(f"{FIG}/01_distribution_cible.png", dpi=110, bbox_inches="tight"); plt.show()
print(df["duree_reelle_min"].describe()[["mean","50%","max"]])
'''.replace("{FIG}", FIG)))

    c.append(md("**Étape 4 — Incidents (label, pas feature).** Fréquence des incidents et leur impact sur la durée."))
    c.append(code(r'''
print((df["incident_type"].value_counts(normalize=True) * 100).round(2).astype(str) + " %")
fig, ax = plt.subplots(figsize=(9, 4))
order = df.groupby("incident_type")["duree_reelle_min"].median().sort_values().index
sns.boxplot(data=df, x="incident_type", y="duree_reelle_min", order=order, ax=ax)
ax.set_title("Durée réelle par type d'incident (les incidents = outliers)"); ax.set_yscale("log")
plt.xticks(rotation=20); plt.tight_layout()
plt.savefig(f"{FIG}/01_incidents_boxplot.png", dpi=110, bbox_inches="tight"); plt.show()
'''.replace("{FIG}", FIG)))

    c.append(md("**Étape 5 — Corrélations.** Relations entre variables numériques et la cible (hors incidents pour la lisibilité)."))
    c.append(code(r'''
num = ["duree_base_s","distance_routiere_m","nb_arrets_restants","nb_montees","nb_descentes",
       "taux_occupation","nb_feux","duree_moyenne_historique_s","retard_cumule_s","duree_reelle_min"]
corr = df[df["incident_type"]=="none"][num].corr()
fig, ax = plt.subplots(figsize=(9, 7))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=ax)
ax.set_title("Corrélations (trajets normaux)")
plt.tight_layout(); plt.savefig(f"{FIG}/01_correlations.png", dpi=110, bbox_inches="tight"); plt.show()
'''.replace("{FIG}", FIG)))

    c.append(md("**Étape 6 — Effets contextuels.** Durée moyenne selon le trafic, la météo, le Ramadan et le moment."))
    c.append(code(r'''
dfn = df[df["incident_type"]=="none"]
fig, ax = plt.subplots(2, 2, figsize=(13, 8))
sns.barplot(data=dfn, x="trafic", y="duree_reelle_min",
            order=["fluide","modere","dense","embouteillage"], ax=ax[0,0]); ax[0,0].set_title("Trafic")
sns.barplot(data=dfn, x="meteo", y="duree_reelle_min",
            order=["ensoleille","nuageux","pluie","brouillard"], ax=ax[0,1]); ax[0,1].set_title("Météo")
sns.barplot(data=dfn, x="ramadan", y="duree_reelle_min", ax=ax[1,0]); ax[1,0].set_title("Ramadan (0/1)")
sns.barplot(data=dfn, x="moment", y="duree_reelle_min", ax=ax[1,1]); ax[1,1].set_title("Moment")
plt.tight_layout(); plt.savefig(f"{FIG}/01_effets_contextuels.png", dpi=110, bbox_inches="tight"); plt.show()
'''.replace("{FIG}", FIG)))

    c.append(md(r'''
**Étape 7 — Préparation (feature engineering).** `features.preparer_features` transforme le brut en matrice
numérique : heure cyclique (sin/cos), one-hot météo/trafic, binaires (Ramadan, souk, travaux, oued),
et numériques. **`incident_type` est exclu** (imprévisible → label, pas feature).
'''))
    c.append(code(r'''
from features import preparer_features, liste_features
X = preparer_features(df)
print("Matrice de features :", X.shape)
print("Colonnes :", list(X.columns))
X.head()
'''))

    c.append(md(r'''
### Conclusion du notebook 01
- Dataset ancré sur les **vraies distances routières OSRM** de Meknès.
- Cible **à queue lourde** : trajets normaux courts + incidents extrêmes (imprévisibles).
- Signaux clairs : trafic, météo, Ramadan, distance de base, historique.
- Features prêtes → **notebook 02 : comparaison de modèles**.
'''))
    nb.cells = c
    return nb


# ══════════════════════════════════════════════════════════════════════
# NOTEBOOK 02 — Comparaison de modèles
# ══════════════════════════════════════════════════════════════════════
def notebook_02():
    nb = nbf.v4.new_notebook()
    c = []
    c.append(md(r'''
# MS12 — Prédiction ETA · Notebook 02 : Comparaison de modèles

**But.** Comparer **plusieurs régresseurs** (pas seulement XGBoost) sur un protocole honnête, puis
**constater le meilleur** à déployer dans FastAPI.

**Protocole (anti-triche).**
- **Split temporel** : les 30 derniers jours d'école = test (jamais vus à l'entraînement) → pas de fuite.
- **Métriques** : MAE (minutes), RMSE, R², MAPE.
- **Double vue** : *tous les trajets* (avec incidents → R² bas, réaliste) vs *trajets normaux* (sans incident).
- **Baseline métier** : la durée OSRM brute (ce qu'on ferait sans ML).
'''))
    c.append(code(SETUP))

    c.append(md("**Étape 1 — Données + split temporel.** On réutilise exactement les fonctions du service (cohérence garantie)."))
    c.append(code(r'''
from train import _charger_dataset, _split_temporel, _metriques, evaluer
from features import preparer_features, liste_features, TARGET, LABEL

df = _charger_dataset()
feat_cols = liste_features(df)
train, test = _split_temporel(df)
Xtr, ytr = preparer_features(train)[feat_cols], train[TARGET].to_numpy()
Xte, yte = preparer_features(test)[feat_cols], test[TARGET].to_numpy()
mask_normal = (test[LABEL].to_numpy() == "none")
print(f"train={len(train)}  test={len(test)}  features={len(feat_cols)}  incidents_test={100*(~mask_normal).mean():.1f}%")
'''))

    c.append(md("**Étape 2 — Benchmark.** On entraîne la baseline OSRM + tous les régresseurs du catalogue, on mesure temps et métriques."))
    c.append(code(r'''
import time
from algorithms import catalogue, BASELINES

rows = []
# Baseline métier : durée OSRM brute (aucun apprentissage)
base_pred = test["duree_base_s"].to_numpy() / 60.0
ev = evaluer(yte, base_pred, mask_normal)
rows.append({"modele":"baseline_osrm","baseline":True,"fit_s":0.0,
             "MAE_tous":ev["tous"]["MAE"],"R2_tous":ev["tous"]["R2"],
             "MAE_normaux":ev["normaux"]["MAE"],"R2_normaux":ev["normaux"]["R2"]})

for nom, est in catalogue(seed=settings.seed).items():
    t0 = time.perf_counter(); est.fit(Xtr, ytr); fit_s = round(time.perf_counter()-t0, 3)
    ev = evaluer(yte, est.predict(Xte), mask_normal)
    rows.append({"modele":nom,"baseline":nom in BASELINES,"fit_s":fit_s,
                 "MAE_tous":ev["tous"]["MAE"],"R2_tous":ev["tous"]["R2"],
                 "MAE_normaux":ev["normaux"]["MAE"],"R2_normaux":ev["normaux"]["R2"]})

res = pd.DataFrame(rows).sort_values("MAE_tous").reset_index(drop=True)
res
'''))

    c.append(md("**Étape 3 — Comparaison visuelle (MAE).** Plus la barre est courte, meilleur est le modèle. La baseline OSRM sert de référence."))
    c.append(code(r'''
fig, ax = plt.subplots(figsize=(10, 5))
colors = ["#c44e52" if b else "#4c72b0" for b in res["baseline"]]
ax.barh(res["modele"], res["MAE_tous"], color=colors)
ax.invert_yaxis(); ax.set_xlabel("MAE (minutes) — tous trajets"); ax.set_title("Comparaison des modèles (MAE)")
for i, v in enumerate(res["MAE_tous"]): ax.text(v, i, f" {v:.2f}", va="center")
plt.tight_layout(); plt.savefig(f"{FIG}/02_mae_comparaison.png", dpi=110, bbox_inches="tight"); plt.show()
'''.replace("{FIG}", FIG)))

    c.append(md("**Étape 4 — R² : tous vs normaux.** Sur *tous* les trajets, le R² est bas (incidents imprévisibles) ; sur les *trajets normaux*, il révèle la vraie qualité prédictive."))
    c.append(code(r'''
sub = res[~res["baseline"]].sort_values("R2_normaux", ascending=False)
x = np.arange(len(sub)); w = 0.38
fig, ax = plt.subplots(figsize=(11, 5))
ax.bar(x-w/2, sub["R2_tous"], w, label="R² tous", color="#8172b3")
ax.bar(x+w/2, sub["R2_normaux"], w, label="R² normaux", color="#55a868")
ax.set_xticks(x); ax.set_xticklabels(sub["modele"], rotation=30, ha="right")
ax.axhline(0.5, ls="--", c="grey", lw=1); ax.set_title("R² : tous vs trajets normaux"); ax.legend()
plt.tight_layout(); plt.savefig(f"{FIG}/02_r2_normal_vs_tous.png", dpi=110, bbox_inches="tight"); plt.show()
'''.replace("{FIG}", FIG)))

    c.append(md("**Étape 5 — On constate le gagnant.** Meilleur MAE (hors baselines) → modèle à déployer dans FastAPI."))
    c.append(code(r'''
candidats = res[~res["baseline"]]
gagnant = candidats.loc[candidats["MAE_tous"].idxmin()]
base_mae = res.loc[res["modele"]=="baseline_osrm","MAE_tous"].iloc[0]
gain = 100*(base_mae - gagnant["MAE_tous"])/base_mae
print(f"🏆 Gagnant : {gagnant['modele']}")
print(f"   MAE tous     = {gagnant['MAE_tous']:.3f} min   (baseline OSRM {base_mae:.3f} → gain {gain:.1f}%)")
print(f"   R² normaux   = {gagnant['R2_normaux']:.3f}   MAE normaux = {gagnant['MAE_normaux']:.3f} min")
'''))

    c.append(md(r'''
### Conclusion du notebook 02
- Le **split temporel** évalue honnêtement la généralisation.
- Sur *tous* les trajets le R² reste bas (incidents = irréductibles) ; sur les *normaux* le meilleur modèle
  atteint la cible visée.
- Le **gagnant** est retenu pour le déploiement → **notebook 03 : stratégie de production** (gel + SHAP).
'''))
    nb.cells = c
    return nb


# ══════════════════════════════════════════════════════════════════════
# NOTEBOOK 03 — Stratégie de production
# ══════════════════════════════════════════════════════════════════════
def notebook_03():
    nb = nbf.v4.new_notebook()
    c = []
    c.append(md(r'''
# MS12 — Prédiction ETA · Notebook 03 : Stratégie de production

**But.** Finaliser le modèle gagnant, l'interpréter (importance des features, SHAP), puis **geler** l'artefact
consommé tel quel par le service FastAPI (`main.py`). C'est le pont entre l'analyse et la production.
'''))
    c.append(code(SETUP))

    c.append(md("**Étape 1 — Entraînement final + gel.** On lance le pipeline complet : benchmark, choix du gagnant, réentraînement sur toutes les données, sauvegarde des artefacts (`eta_model.pkl`, `eta_config.json`, `benchmark_summary.json`)."))
    c.append(code(r'''
import train
train.main()
config = json.load(open(settings.config_path, encoding="utf-8"))
print("Algorithme gelé :", config["algorithme"], "| version", config["version"])
print("Métriques test (normaux) :", config["metrics_test"]["normaux"])
print("Gain vs baseline OSRM :", config["gain_vs_baseline_%"], "%")
'''))

    c.append(md("**Étape 2 — Prédit vs réel.** On charge le modèle gelé et on trace la prédiction contre la réalité sur le test (les incidents ressortent en rouge = non prédictibles)."))
    c.append(code(r'''
import joblib
from train import _charger_dataset, _split_temporel
from features import preparer_features, TARGET, LABEL

model = joblib.load(settings.model_path)
df = _charger_dataset(); _, test = _split_temporel(df)
Xte = preparer_features(test)[config["feature_columns"]]
pred = model.predict(Xte); yte = test[TARGET].to_numpy(); inc = test[LABEL].to_numpy() != "none"

fig, ax = plt.subplots(figsize=(6.5, 6.5))
ax.scatter(yte[~inc], pred[~inc], s=12, alpha=.5, label="normaux", color="#4c72b0")
ax.scatter(yte[inc], pred[inc], s=25, alpha=.8, label="incidents", color="#c44e52")
lim = [0, np.percentile(yte, 99)]
ax.plot(lim, lim, "k--", lw=1); ax.set_xlim(lim); ax.set_ylim(lim)
ax.set_xlabel("durée réelle (min)"); ax.set_ylabel("durée prédite (min)")
ax.set_title("Prédit vs réel (test)"); ax.legend()
plt.tight_layout(); plt.savefig(f"{FIG}/03_predit_vs_reel.png", dpi=110, bbox_inches="tight"); plt.show()
'''.replace("{FIG}", FIG)))

    c.append(md("**Étape 3 — Résidus.** Les résidus des trajets normaux doivent être centrés et resserrés."))
    c.append(code(r'''
resid = pred - yte
fig, ax = plt.subplots(figsize=(9, 4))
ax.hist(resid[~inc], bins=50, color="#55a868")
ax.axvline(0, c="k", ls="--", lw=1); ax.set_title("Résidus (trajets normaux)"); ax.set_xlabel("prédit - réel (min)")
plt.tight_layout(); plt.savefig(f"{FIG}/03_residus.png", dpi=110, bbox_inches="tight"); plt.show()
print("Résidu normaux : moyenne=%.3f  écart-type=%.3f min" % (resid[~inc].mean(), resid[~inc].std()))
'''.replace("{FIG}", FIG)))

    c.append(md("**Étape 4 — Importance des features.** Ce qui pilote la prédiction (issu de `eta_config.json`)."))
    c.append(code(r'''
imp = config.get("importances", {})
if imp:
    s = pd.Series(imp).sort_values()
    fig, ax = plt.subplots(figsize=(9, 6))
    s.plot.barh(ax=ax, color="#4c72b0"); ax.set_title(f"Importance des features — {config['algorithme']}")
    plt.tight_layout(); plt.savefig(f"{FIG}/03_importances.png", dpi=110, bbox_inches="tight"); plt.show()
else:
    print("Pas d'importances exposées par ce modèle.")
'''.replace("{FIG}", FIG)))

    c.append(md("**Étape 5 — SHAP (optionnel).** Explication fine des contributions (si `shap` est installé et le modèle compatible)."))
    c.append(code(r'''
try:
    import shap
    est = model.steps[-1][1] if hasattr(model, "steps") else model
    Xs = Xte.sample(min(300, len(Xte)), random_state=42)
    explainer = shap.Explainer(est, Xs)
    sv = explainer(Xs)
    shap.plots.beeswarm(sv, max_display=12, show=False)
    plt.tight_layout(); plt.savefig(f"{FIG}/03_shap.png", dpi=110, bbox_inches="tight"); plt.show()
except Exception as e:
    print("SHAP ignoré :", e)
'''.replace("{FIG}", FIG)))

    c.append(md("**Étape 6 — Config gelée (consommée par FastAPI).** Le service `main.py` charge ce même artefact — zéro divergence entre l'analyse et la production."))
    c.append(code(r'''
print(json.dumps({k: config[k] for k in
     ["version","algorithme","cible","n_lignes","n_features","mae_minutes","gain_vs_baseline_%","dateCalcul"]},
     indent=2, ensure_ascii=False))
print("\nArtefacts :", settings.model_path, "|", settings.config_path, "|", settings.benchmark_path)
'''))

    c.append(md(r'''
### Conclusion du notebook 03
- Modèle gagnant **réentraîné sur toutes les données** et **gelé** (`eta_model.pkl` + `eta_config.json`).
- Interprétabilité fournie (importances / SHAP) pour le mémoire.
- Le service **MS12** (`POST /api/eta/predict`) sert exactement ce modèle → cohérence garantie.
'''))
    nb.cells = c
    return nb


def main():
    notebooks = {
        "01_eta_data_study.ipynb": notebook_01(),
        "02_model_comparison.ipynb": notebook_02(),
        "03_production_strategy.ipynb": notebook_03(),
    }
    for name, nb in notebooks.items():
        path = os.path.join(HERE, name)
        with open(path, "w", encoding="utf-8") as f:
            nbf.write(nb, f)
        print("écrit :", path)


if __name__ == "__main__":
    main()
