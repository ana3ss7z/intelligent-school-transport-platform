"""
Génère le notebook CRISP-DM de MS11 (détection d'anomalies) via nbformat.
Markdown explicatif avant chaque cellule de code (même standard que MS6/MS12).

Usage : python notebooks/build_notebooks.py
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))

SETUP = r'''
import os, sys, json, warnings
warnings.filterwarnings("ignore")
while os.path.basename(os.getcwd()) == "notebooks":
    os.chdir("..")
sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd
import matplotlib.pyplot as plt, seaborn as sns
sns.set_theme(style="whitegrid", palette="deep")
os.makedirs("notebooks/figures", exist_ok=True)
FIG = "notebooks/figures"
from config import settings
print("Répertoire de travail :", os.getcwd())
'''


def md(s): return nbf.v4.new_markdown_cell(s.strip("\n"))
def code(s): return nbf.v4.new_code_cell(s.strip("\n"))


def notebook_04():
    nb = nbf.v4.new_notebook()
    c = []
    c.append(md(r'''
# MS11 — Détection d'anomalies · Notebook 04 (CRISP-DM)

**Objectif métier.** Repérer automatiquement les **trajets anormaux** (incidents) pour alerter l'administration.

**Dataset propre à MS11** (`data/anomaly_dataset.csv`) avec des **anomalies hétérogènes et contextuelles** :
- **franc** (panne/accident) : durée énorme → ratio très élevé (facile) ;
- **contextuel** : ratio modéré MAIS par conditions légères (fluide) → anormal *vu le contexte* ;
- **surcharge** : durée quasi normale mais montées/descentes anormales.

**Thèse du notebook.** Aucune variable seule ne capte les 3 natures → il faut **du feature engineering**
(`surprise` = ratio ajusté au contexte) **et** un détecteur **multivarié curé** (Isolation Forest).
Modèle **non supervisé** ; le label `incident_type` sert **uniquement à évaluer**.
'''))
    c.append(md("**Étape 0 — Environnement.**"))
    c.append(code(SETUP))

    c.append(md("**Étape 1 — Données.** On génère le dataset d'anomalies s'il n'existe pas, puis on le charge."))
    c.append(code(r'''
from features import label_binaire, build, CURATED, colonnes_all
if not os.path.exists(settings.dataset_path):
    import dataset_anomaly
    dataset_anomaly.generer().to_csv(settings.dataset_path, index=False)
df = pd.read_csv(settings.dataset_path)
y = label_binaire(df)
print("Trajets :", len(df), "| incidents :", int(y.sum()), f"({100*y.mean():.2f}%)")
print(df["incident_type"].value_counts())
'''))

    c.append(md("**Étape 2 — EDA : `ratio` vs `surprise`.** Le `ratio` brut ne sépare pas les anomalies **contextuelles** (elles ressemblent à un trajet de trafic dense). La `surprise` (= ratio ajusté au contexte) les fait ressortir."))
    c.append(code(r'''
F = build(df)
fig, ax = plt.subplots(1, 2, figsize=(13, 4))
for lab, col, name in [(0, "#55a868", "normal"), (1, "#c44e52", "incident")]:
    ax[0].hist(F["ratio"][y == lab], bins=60, alpha=.6, label=name, color=col)
    ax[1].hist(F["surprise"][y == lab], bins=60, alpha=.6, label=name, color=col)
ax[0].set_yscale("log"); ax[0].set_title("ratio brut"); ax[0].set_xlabel("ratio"); ax[0].legend()
ax[1].set_yscale("log"); ax[1].set_title("surprise (ratio ajusté au contexte)"); ax[1].set_xlabel("surprise"); ax[1].legend()
plt.tight_layout(); plt.savefig(f"{FIG}/04_ratio_vs_surprise.png", dpi=110, bbox_inches="tight"); plt.show()
'''))

    c.append(md("**Étape 3 — Benchmark de 4 détecteurs.** 2 seuils univariés (ratio, surprise) vs 2 Isolation Forest (toutes features = *dilué*, features *curées*). Split temporel, évaluation à budget d'alerte fixe."))
    c.append(code(r'''
from train_anomaly import _split_temporel, _evaluer
from anomaly import AnomalyDetector

train, test = _split_temporel(df)
ytr, yte = label_binaire(train), label_binaire(test)
contam = float(min(0.2, max(0.01, ytr.mean())))
cols_all = colonnes_all(df)

detecteurs = {
    "seuil_ratio":     AnomalyDetector("seuil_ratio", "threshold", contam, threshold_col="ratio"),
    "seuil_surprise":  AnomalyDetector("seuil_surprise", "threshold", contam, threshold_col="surprise"),
    "iforest_all":     AnomalyDetector("iforest_all", "iforest", contam, settings.seed, feature_cols=cols_all),
    "iforest_curated": AnomalyDetector("iforest_curated", "iforest", contam, settings.seed, feature_cols=CURATED),
}
scores_test, rows = {}, []
for nom, det in detecteurs.items():
    det.fit(train); s = det.scores(test); scores_test[nom] = s
    pred = s >= np.quantile(s, 1 - contam)
    m = _evaluer(yte.to_numpy(), s, pred)
    rows.append({"detecteur": nom, "PR_AUC": m["PR_AUC"], "ROC_AUC": m["ROC_AUC"],
                 "F1": m["F1"], "precision": m["precision"], "rappel": m["rappel"]})
res = pd.DataFrame(rows).sort_values("PR_AUC", ascending=False).reset_index(drop=True)
res
'''))

    c.append(md("**Étape 4 — Courbes ROC & Précision-Rappel.**"))
    c.append(code(r'''
from sklearn.metrics import roc_curve, precision_recall_curve
fig, ax = plt.subplots(1, 2, figsize=(13, 5))
for nom, s in scores_test.items():
    fpr, tpr, _ = roc_curve(yte, s); ax[0].plot(fpr, tpr, label=nom)
    prec, rec, _ = precision_recall_curve(yte, s); ax[1].plot(rec, prec, label=nom)
ax[0].plot([0, 1], [0, 1], "k--", lw=1); ax[0].set_title("ROC"); ax[0].set_xlabel("FPR"); ax[0].set_ylabel("TPR"); ax[0].legend()
ax[1].set_title("Précision-Rappel"); ax[1].set_xlabel("Rappel"); ax[1].set_ylabel("Précision"); ax[1].legend()
plt.tight_layout(); plt.savefig(f"{FIG}/04_courbes_roc_pr.png", dpi=110, bbox_inches="tight"); plt.show()
'''))

    c.append(md("**Étape 5 — Matrice de confusion du gagnant** (budget d'alerte fixe)."))
    c.append(code(r'''
from sklearn.metrics import confusion_matrix
best = res.iloc[0]["detecteur"]; s = scores_test[best]
pred = s >= np.quantile(s, 1 - contam)
cm = confusion_matrix(yte, pred)
fig, ax = plt.subplots(figsize=(4.5, 4))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
            xticklabels=["normal", "anomalie"], yticklabels=["normal", "incident"], ax=ax)
ax.set_title(f"Confusion — {best}"); ax.set_xlabel("prédit"); ax.set_ylabel("réel")
plt.tight_layout(); plt.savefig(f"{FIG}/04_confusion.png", dpi=110, bbox_inches="tight"); plt.show()
print("Gagnant :", best)
'''))

    c.append(md(r'''
**Étape 6 — Interprétation (honnête, triple leçon).**
1. **Le feature engineering prime** : `surprise` (contextuel) sépare mieux que le `ratio` brut.
2. **La curation prime** : `iforest_curated` ≫ `iforest_all` — trop de features **diluent** le signal (Isolation
   Forest traite toutes les dimensions à égalité).
3. **Le multivarié gagne ICI** parce que les anomalies sont **hétérogènes** (franc + contextuel + surcharge) :
   aucun seuil univarié ne les capte toutes ; le détecteur curé les combine.
'''))
    c.append(md("**Étape 7 — Gel du modèle de production** (benchmark → gagnant → réentraînement sur tout → artefacts)."))
    c.append(code(r'''
import train_anomaly
train_anomaly.main()
cfg = json.load(open(settings.config_path, encoding="utf-8"))
print(json.dumps({k: cfg[k] for k in ["detecteur","kind","feature_cols","threshold","contamination","metrics_test","taux_incidents_%"]},
                 indent=2, ensure_ascii=False))
'''))
    c.append(md(r'''
### Conclusion
- Détecteur gelé (`anomaly_model.pkl`) servi par **MS11** (`POST /api/analytique/anomalies`, `GET .../scan`).
- Boucle DS : les incidents que l'**ETA (MS12)** ne peut pas prédire sont ceux que la **détection
  d'anomalies (MS11)** isole — grâce au feature engineering contextuel et à un modèle multivarié curé.
'''))
    nb.cells = c
    return nb


def main():
    path = os.path.join(HERE, "04_anomaly_detection.ipynb")
    with open(path, "w", encoding="utf-8") as f:
        nbf.write(notebook_04(), f)
    print("écrit :", path)


if __name__ == "__main__":
    main()
