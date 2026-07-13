"""
Génère le notebook d'étude VRP de MS5 (via nbformat).
Markdown explicatif avant chaque cellule ; figures exportées (route optimisée, baseline vs optimisé, gains).
Consomme les groupes RÉELS produits par MS6 (via MS2) — pas de clustering « bis ».

Usage : python notebooks/build_notebooks.py
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))

SETUP = r'''
import os, sys, asyncio, warnings
warnings.filterwarnings("ignore")
while os.path.basename(os.getcwd()) == "notebooks":
    os.chdir("..")
sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": .3,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold"})
os.makedirs("notebooks/figures", exist_ok=True)
FIG = "notebooks/figures"
from config import settings
from osrm_client import matrice, geometrie
from vrp import solve_tsp, baseline_plus_proche, cout_tournee
ECOLE = (settings.ecole_lat, settings.ecole_lng)
print("Répertoire :", os.getcwd(), "| École (dépôt) :", ECOLE)
'''


def md(s): return nbf.v4.new_markdown_cell(s.strip("\n"))
def code(s): return nbf.v4.new_code_cell(s.strip("\n"))


def notebook_05():
    nb = nbf.v4.new_notebook()
    c = []
    c.append(md(r'''
# MS5 — Optimisation de tournées (VRP) · Notebook 05

**Objectif.** Une fois les élèves affectés aux bus par le **clustering (MS6)**, déterminer **l'ordre de passage
optimal** de chaque bus pour **minimiser le temps de trajet**.

**Modèle.** Pour un bus, c'est un **TSP** (voyageur de commerce) : dépôt = **école**, le bus part de l'école,
ramasse tous ses élèves, revient à l'école. Résolu par **OR-Tools** sur les **durées routières OSRM réelles**.
On compare à une **baseline** (« plus proche voisin ») pour mesurer le **gain**.
'''))
    c.append(md("**Étape 0 — Environnement.**"))
    c.append(code(SETUP))

    c.append(md(r'''
**Étape 1 — Données & groupes RÉELS (MS6).** On **ne recrée pas** de clustering : on consomme les groupes
**réellement produits par MS6** et appliqués dans MS2 (`groupeId`). C'est la cohérence du projet intégré —
le VRP route l'affectation existante. *(Prérequis : MS2 démarré + `POST /api/clustering/production?appliquer=true`.)*
'''))
    c.append(code(r'''
from ms2_client import get_all_eleves
eleves = await get_all_eleves()          # MS2 = source de vérité (groupes MS6 appliqués)
df = pd.DataFrame(eleves)
df = df[df["groupeId"].notna() & df["latitude"].notna()].copy()
df["bus"] = df["groupeId"].astype(int)
assert len(df) > 0, "Aucun groupe en base — lancer le clustering MS6 (appliquer=true) d'abord."
print("Élèves affectés :", len(df), "| bus (groupes MS6) :", df["bus"].nunique())
print(df["bus"].value_counts().sort_index().to_dict())
'''))

    c.append(md("**Étape 2 — Optimiser TOUS les bus.** Pour chaque bus : matrice OSRM → OR-Tools (optimisé) vs baseline (glouton). On stocke tout et on retient le bus au **plus fort gain** pour l'illustration."))
    c.append(code(r'''
res = {}
for b in sorted(df["bus"].unique()):
    g = df[df["bus"] == b]
    if len(g) < 3:
        continue
    pts = [ECOLE] + list(zip(g["latitude"], g["longitude"]))
    dur, dist = await matrice(pts)
    opt = solve_tsp(dur, depot=0, time_limit_s=5)
    base = baseline_plus_proche(dur, depot=0)
    cb, co = cout_tournee(base, dur), cout_tournee(opt, dur)
    res[b] = {"pts": pts, "dur": dur, "opt": opt, "base": base, "n": len(g),
              "base_min": cb / 60, "opt_min": co / 60, "gain": 100 * (cb - co) / cb if cb else 0}

tab = pd.DataFrame([{"bus": b, "n": r["n"], "baseline_min": round(r["base_min"], 1),
                     "optimise_min": round(r["opt_min"], 1), "gain_%": round(r["gain"], 1)}
                    for b, r in res.items()])
show = max(res, key=lambda b: res[b]["gain"])   # bus le plus parlant
print("Gain moyen flotte : %.1f %%  |  bus illustré (gain max) : %d" %
      (np.mean([r["gain"] for r in res.values()]), show))
tab
'''))

    c.append(md("**Étape 3 — Comparaison visuelle** (bus au plus fort gain) : ordre naïf (gauche) vs ordre optimisé (droite). Les lignes relient les arrêts dans l'ordre de visite ; 🏫 = école (dépôt). Les deux tracés **diffèrent nettement**."))
    c.append(code(r'''
R = res[show]; pts = R["pts"]
def trace(ax, order, titre, color):
    xy = np.array([pts[i] for i in order])
    ax.plot(xy[:, 1], xy[:, 0], "-o", color=color, ms=5, lw=1.5)
    ax.plot(ECOLE[1], ECOLE[0], marker="*", color="black", ms=18)
    ax.set_title(titre); ax.set_xlabel("lng"); ax.set_ylabel("lat")
fig, ax = plt.subplots(1, 2, figsize=(13, 5.5), sharex=True, sharey=True)
trace(ax[0], R["base"], f"Baseline — {R['base_min']:.1f} min", "#C44E52")
trace(ax[1], R["opt"], f"OR-Tools optimisé — {R['opt_min']:.1f} min (gain {R['gain']:.0f}%)", "#4C72B0")
fig.suptitle(f"Bus {show} — {R['n']} élèves", fontweight="bold")
plt.tight_layout(); plt.savefig(f"{FIG}/05_baseline_vs_optimise.png", bbox_inches="tight"); plt.show()
'''))

    c.append(md("**Étape 4 — Tournée optimale sur le réseau routier réel** (géométrie OSRM), ordre de passage numéroté."))
    c.append(code(r'''
geom = np.array(await geometrie([pts[i] for i in R["opt"]]))
xy = np.array([pts[i] for i in R["opt"]])
fig, ax = plt.subplots(figsize=(8.5, 7))
if len(geom):
    ax.plot(geom[:, 1], geom[:, 0], "-", color="#4C72B0", lw=2, alpha=.8, label="itinéraire OSRM")
ax.scatter(xy[1:-1, 1], xy[1:-1, 0], c="#DD8452", s=60, zorder=5, edgecolor="k", label="arrêts élèves")
for rank, i in enumerate([n for n in R["opt"] if n != 0], 1):
    ax.annotate(str(rank), (pts[i][1], pts[i][0]), fontsize=8, ha="center", va="center")
ax.plot(ECOLE[1], ECOLE[0], marker="*", color="black", ms=22, label="école (dépôt)")
ax.set_title(f"Tournée optimale bus {show} (réseau OSRM)"); ax.set_xlabel("lng"); ax.set_ylabel("lat"); ax.legend()
plt.tight_layout(); plt.savefig(f"{FIG}/05_tournee_reelle.png", bbox_inches="tight"); plt.show()
'''))

    c.append(md("**Étape 5 — Gain sur toute la flotte** (OR-Tools vs baseline, par bus)."))
    c.append(code(r'''
labels = [f"bus {b}" for b in res]; gains = [res[b]["gain"] for b in res]
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(labels, gains, color="#55A868")
ax.axhline(np.mean(gains), ls="--", color="k", label=f"moyenne {np.mean(gains):.1f} %")
ax.set_ylabel("gain vs baseline (%)"); ax.set_title("Gain OR-Tools par bus"); ax.legend()
for i, v in enumerate(gains): ax.text(i, v, f"{v:.0f}", ha="center", va="bottom", fontsize=8)
plt.tight_layout(); plt.savefig(f"{FIG}/05_gains_flotte.png", bbox_inches="tight"); plt.show()
'''))

    c.append(md(r'''
**Étape 6 — Matin vs Soir : pourquoi le soir garde le MÊME ordre (pas l'inverse).** La tournée optimale est
un **cycle**. On pourrait croire que le soir (dépose) doit **inverser** l'ordre du matin (ramassage). En fait,
sur une matrice symétrique le coût total serait identique ; le vrai critère est le **temps passé à bord par
élève**. Garder le **même ordre** équilibre ce temps sur la journée (matin + soir ≈ une durée de tournée pour
**tout le monde**), alors que l'inverser **pénalise deux fois** l'élève ramassé en premier le matin.
'''))
    c.append(code(r'''
def temps_a_bord(order, M, mode):
    """Temps à bord par nœud-élève. order=[0,...,0] (0=école). ramassage: de l'élève à la fin ;
    depose: de l'école (début) jusqu'à l'élève."""
    out = {}
    for t in range(1, len(order) - 1):
        node = order[t]
        out[node] = cout_tournee(order[t:], M) if mode == "ramassage" else cout_tournee(order[:t + 1], M)
    return out

R = res[show]; dur = R["dur"]; order = R["opt"]
rev = [0] + [i for i in order if i != 0][::-1] + [0]         # cycle inversé
matin    = temps_a_bord(order, dur, "ramassage")
soir_mm  = temps_a_bord(order, dur, "depose")                # dépose MÊME ordre
soir_inv = temps_a_bord(rev,   dur, "depose")                # dépose ordre INVERSÉ
nodes = [i for i in order if i != 0]
tot_mm  = np.array([(matin[n] + soir_mm[n]) / 60 for n in nodes])
tot_inv = np.array([(matin[n] + soir_inv[n]) / 60 for n in nodes])
asym = max(abs(dur[i][j] - dur[j][i]) for i in range(len(dur)) for j in range(len(dur)))
print(f"Bus {show} — matrice {'ASYMÉTRIQUE (OSRM réel)' if asym>1e-6 else 'symétrique'} (asym max {asym:.0f}s)")
print(f"Coût total tournée : même-ordre {cout_tournee(order,R['dur'])/60:.1f} min | inversé {cout_tournee(rev,R['dur'])/60:.1f} min")
pd.DataFrame({"même_ordre_min": np.round(tot_mm,1), "inversé_min": np.round(tot_inv,1)}).describe().loc[["max","mean","std"]]
'''))
    c.append(md("**Temps à bord par élève sur la journée** (matin + soir). À gauche « même ordre » : barres quasi **égales** (équité). À droite « inversé » : très **dispersé**, l'élève du bout est puni deux fois."))
    c.append(code(r'''
x = np.arange(len(nodes))
fig, ax = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
ax[0].bar(x, tot_mm, color="#55A868"); ax[0].axhline(tot_mm.mean(), ls="--", c="k", label=f"moy {tot_mm.mean():.1f}")
ax[0].set_title(f"MÊME ordre — écart-type {tot_mm.std():.2f} min (équitable)"); ax[0].legend()
ax[1].bar(x, tot_inv, color="#C44E52"); ax[1].axhline(tot_inv.mean(), ls="--", c="k", label=f"moy {tot_inv.mean():.1f}")
ax[1].set_title(f"Ordre INVERSÉ — écart-type {tot_inv.std():.2f} min (inéquitable)"); ax[1].legend()
for a in ax: a.set_xlabel("élève (ordre de passage)"); a.set_ylabel("temps à bord jour (min)")
plt.tight_layout(); plt.savefig(f"{FIG}/05_equite_matin_soir.png", bbox_inches="tight"); plt.show()
'''))

    c.append(md(r'''
### Conclusion
- **OR-Tools** ordonne chaque tournée sur les **distances routières réelles** (OSRM), avec un **gain mesurable**
  vs un ordre naïf (variable selon la compacité du groupe : un petit groupe compact peut déjà être optimal).
- **Complémentarité** : MS6 décide **qui** va dans quel bus (capacité) ; MS5 décide **dans quel ordre** (temps).
- **Matin vs soir** : le soir garde le **même ordre** que le matin (dépose sur la même tournée). C'est **plus
  équitable** (temps à bord égal sur la journée) et, sur les vraies routes OSRM **asymétriques**, l'ordre inversé
  n'étant pas ré-optimisé, il coûte **aussi plus cher** — donc doublement à éviter. Preuve : `verify_sens.py`.
- Servi par **MS5** : `POST /api/planification/tournee?groupeId=` et `/tournees`.
- **Suite (S11)** : CVRP global (assignation + routage conjoints) + benchmark vs l'approche MS6+TSP.
'''))
    nb.cells = c
    return nb


def main():
    path = os.path.join(HERE, "05_vrp_study.ipynb")
    with open(path, "w", encoding="utf-8") as f:
        nbf.write(notebook_05(), f)
    print("écrit :", path)


if __name__ == "__main__":
    main()
