"""
Génère le notebook CRISP-DM de MS11 (détection d'anomalies) via nbformat.
Markdown explicatif avant chaque cellule de code (même standard que MS6/MS12).

Usage : python notebooks/build_notebooks.py
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = "notebooks/figures"

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

**Objectif métier.** Détecter automatiquement les **trajets anormaux** (pannes, accidents, routes bloquées…)
à partir des données de trajet, afin d'alerter l'administration.

**Idée clé.** MS12 a généré un label `incident_type` (incidents **imprévisibles** au départ, donc exclus des
features ETA). Ici on fait l'inverse : sur des trajets **déjà observés**, on **détecte** ces incidents avec un
modèle **non supervisé** (Isolation Forest). Le label sert **uniquement à évaluer** (jamais à entraîner).

**Démarche honnête.** Split temporel, benchmark de détecteurs, évaluation à budget d'alerte fixe
(PR-AUC/ROC-AUC/F1), puis on garde le meilleur — même logique que MS6/MS12.
'''))
    c.append(md("**Étape 0 — Environnement.**"))
    c.append(code(SETUP))

    c.append(md("**Étape 1 — Chargement.** On lit le dataset ETA de MS12 (contient `duree_reelle_min`, `duree_base_s`, contexte et le label `incident_type`)."))
    c.append(code(r'''
from features import label_binaire, build
df = pd.read_csv(settings.eta_dataset_path)
y = label_binaire(df)
print("Trajets :", len(df), "| incidents :", int(y.sum()), f"({100*y.mean():.2f}%)")
print(df["incident_type"].value_counts())
'''))

    c.append(md("**Étape 2 — EDA : le signal `ratio = durée réelle / durée de base`.** Les incidents allongent fortement le trajet → le ratio explose. On visualise sa distribution (échelle log) selon normal vs incident."))
    c.append(code(r'''
ratio = (df["duree_reelle_min"] * 60) / df["duree_base_s"].clip(lower=1)
fig, ax = plt.subplots(figsize=(10, 4))
ax.hist(ratio[y == 0], bins=60, alpha=.7, label="normal", color="#55a868")
ax.hist(ratio[y == 1], bins=60, alpha=.7, label="incident", color="#c44e52")
ax.set_yscale("log"); ax.set_xlabel("ratio durée réelle / base"); ax.set_title("Séparation par le ratio")
ax.legend(); plt.tight_layout(); plt.savefig(f"{FIG}/04_ratio_distribution.png", dpi=110, bbox_inches="tight"); plt.show()
print("ratio normal (méd) =", round(float(ratio[y==0].median()),2), "| incident (méd) =", round(float(ratio[y==1].median()),2))
'''.replace("{FIG}", FIG)))

    c.append(md("**Étape 3 — Benchmark de 3 détecteurs.** (a) Isolation Forest sur le **contexte seul** (aveugle au résultat), (b) IF sur **contexte + ratio**, (c) **seuil simple sur le ratio**. Split temporel, évaluation à budget d'alerte fixe."))
    c.append(code(r'''
from train_anomaly import _split_temporel, _evaluer
from anomaly import AnomalyDetector

train, test = _split_temporel(df)
ytr, yte = label_binaire(train), label_binaire(test)
contam = float(min(0.2, max(0.01, ytr.mean())))

detecteurs = {
    "iforest_contexte": AnomalyDetector("iforest", contam, settings.seed, with_outcome=False),
    "iforest_ratio":    AnomalyDetector("iforest", contam, settings.seed, with_outcome=True),
    "seuil_ratio":      AnomalyDetector("ratio", contam, settings.seed),
}
scores_test = {}
rows = []
for nom, det in detecteurs.items():
    det.fit(train)
    s = det.scores(test); scores_test[nom] = s
    thr = float(np.quantile(s, 1 - contam)); pred = s >= thr
    m = _evaluer(yte.to_numpy(), s, pred)
    rows.append({"detecteur": nom, "PR_AUC": m["PR_AUC"], "ROC_AUC": m["ROC_AUC"],
                 "F1": m["F1"], "precision": m["precision"], "rappel": m["rappel"]})
res = pd.DataFrame(rows).sort_values("PR_AUC", ascending=False).reset_index(drop=True)
res
'''))

    c.append(md("**Étape 4 — Courbes ROC & Précision-Rappel.** On visualise le pouvoir de séparation de chaque détecteur (indépendant du seuil)."))
    c.append(code(r'''
from sklearn.metrics import roc_curve, precision_recall_curve
fig, ax = plt.subplots(1, 2, figsize=(13, 5))
for nom, s in scores_test.items():
    fpr, tpr, _ = roc_curve(yte, s); ax[0].plot(fpr, tpr, label=nom)
    prec, rec, _ = precision_recall_curve(yte, s); ax[1].plot(rec, prec, label=nom)
ax[0].plot([0, 1], [0, 1], "k--", lw=1); ax[0].set_title("ROC"); ax[0].set_xlabel("FPR"); ax[0].set_ylabel("TPR"); ax[0].legend()
ax[1].set_title("Précision-Rappel"); ax[1].set_xlabel("Rappel"); ax[1].set_ylabel("Précision"); ax[1].legend()
plt.tight_layout(); plt.savefig(f"{FIG}/04_courbes_roc_pr.png", dpi=110, bbox_inches="tight"); plt.show()
'''.replace("{FIG}", FIG)))

    c.append(md("**Étape 5 — Matrice de confusion du gagnant.** À budget d'alerte fixe (top contamination%)."))
    c.append(code(r'''
from sklearn.metrics import confusion_matrix
best = res.iloc[0]["detecteur"]
s = scores_test[best]; pred = s >= np.quantile(s, 1 - contam)
cm = confusion_matrix(yte, pred)
fig, ax = plt.subplots(figsize=(4.5, 4))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
            xticklabels=["normal", "anomalie"], yticklabels=["normal", "incident"], ax=ax)
ax.set_title(f"Confusion — {best}"); ax.set_xlabel("prédit"); ax.set_ylabel("réel")
plt.tight_layout(); plt.savefig(f"{FIG}/04_confusion.png", dpi=110, bbox_inches="tight"); plt.show()
print("Gagnant :", best)
'''))

    c.append(md(r'''
**Étape 6 — Interprétation (honnête).**
- Le **ratio réel/base** est un signal quasi-unidimensionnel très fort → un **seuil simple** attrape
  ~100 % des incidents.
- **Isolation Forest** confirme (ROC-AUC élevé) mais n'apporte pas de gain multivarié **ici**, car le signal
  est de faible dimension — un résultat de **parcimonie** (le modèle simple suffit), comme XGBoost vs
  elasticnet dans MS12. IF reste le **détecteur général** pour des anomalies plus subtiles/multivariées.
'''))
    c.append(md("**Étape 7 — Gel du modèle de production.** On lance le pipeline complet : benchmark, choix du gagnant, réentraînement sur toutes les données, sauvegarde des artefacts consommés par le service MS11."))
    c.append(code(r'''
import train_anomaly
train_anomaly.main()
cfg = json.load(open(settings.config_path, encoding="utf-8"))
print(json.dumps({k: cfg[k] for k in ["detecteur","approach","threshold","contamination","metrics_test","taux_incidents_%"]},
                 indent=2, ensure_ascii=False))
'''))
    c.append(md(r'''
### Conclusion
- Détecteur gelé (`anomaly_model.pkl`) servi par **MS11** (`POST /api/analytique/anomalies`, `GET .../scan`).
- Boucle DS complète : les incidents que l'**ETA (MS12)** ne peut pas prédire sont ceux que la
  **détection d'anomalies (MS11)** isole — les deux services partagent le même dataset.
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
