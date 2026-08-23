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


# ─────────────────────────────────────────────────────────────────────────────
# Notebook 06 — Benchmark CVRP global vs MS6 + TSP
# ─────────────────────────────────────────────────────────────────────────────

SETUP_06 = r'''
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
from osrm_client import matrice
from ms2_client import get_all_eleves
from vrp import solve_tsp, cout_tournee
from cvrp import solve_cvrp, cout_routes, charges, bus_utilises, chronometre
ECOLE = (settings.ecole_lat, settings.ecole_lng)

# Budget de résolution PAR BUS. L'approche A résout k TSP de BUDGET s chacune ;
# l'approche B reçoit donc k × BUDGET pour son unique résolution. Sans cette
# égalisation, on comparerait deux efforts de calcul différents.
BUDGET_PAR_BUS_S = 5
CAPACITE = 50          # même valeur que BUS_CAPACITY de MS6
print("Répertoire :", os.getcwd(), "| École (dépôt) :", ECOLE)
'''


def notebook_06():
    nb = nbf.v4.new_notebook()
    c = []
    c.append(md(r'''
# MS5 — Benchmark : CVRP global vs MS6 + TSP

## La question

L'architecture de production **décompose** le problème en deux : **MS6** affecte les élèves aux bus
sous contrainte de capacité (k-médoïdes capacitaire sur distance routière), puis **MS5** résout un
**TSP par bus** pour l'ordre de passage.

C'est confortable, mais *a priori* sous-optimal : l'affectation est figée **avant** de connaître le
coût des tournées qui en découlent. Un **CVRP** résout les deux décisions d'un bloc.

> **Combien nous coûte cette décomposition ?**

Le résultat est exploitable dans les deux sens — et c'est ce qui en fait un vrai benchmark :
* si le CVRP **gagne nettement**, on quantifie le prix de la décomposition ;
* s'il **gagne peu ou perd**, c'est une **validation** de MS6→MS5, car la décomposition de MS6 n'est
  pas arbitraire : elle est **géographiquement informée** (k-médoïdes sur distance routière OSRM),
  là où le CVRP part à froid.

## Le protocole (ce qui rend la comparaison honnête)

| Règle | Pourquoi |
|---|---|
| **Une seule matrice OSRM**, construite une fois ; l'approche A en extrait ses sous-matrices | Sinon on compare deux jeux de distances |
| **Même grandeur minimisée** : la durée (s) | `vrp.solve_tsp` minimise la durée ; le CVRP doit faire pareil |
| **Même arrondi entier** de la matrice | OR-Tools travaille en entiers ; même perte de précision des deux côtés |
| **Budget égalisé** : A = k TSP × B s ; B = 1 résolution de k × B s | Sinon on compare deux efforts de calcul |
| **Même nombre de bus** (k = nombre de groupes MS6) et **même capacité** | Sinon le CVRP triche en ajoutant des véhicules |

On mesure aussi le **temps de résolution** et **l'équilibrage des charges** : un CVRP qui gagne 3 %
en distance mais met dix minutes, ou qui charge un bus à 50 et un autre à 12, n'est pas un gagnant
en exploitation.
'''))
    c.append(code(SETUP_06))

    c.append(md(r'''
## 1. Les données réelles

On consomme les **groupes produits par MS6** (via MS2) — pas un clustering « bis » refait pour
l'occasion. Le périmètre est paramétrable : comparer sur 2, 3 puis 4 groupes permet de voir si
l'écart entre les deux approches **grandit avec la taille** du problème, ce qui est la vraie
question (un CVRP se dégrade quand l'instance grossit).
'''))
    c.append(code(r'''
eleves = await get_all_eleves()
valides = [e for e in eleves
           if e.get("latitude") is not None and e.get("longitude") is not None
           and e.get("groupeId") not in (None, 999)]
groupes = {}
for e in valides:
    groupes.setdefault(e["groupeId"], []).append(e)
groupes = dict(sorted(groupes.items()))
print(f"{len(valides)} élèves répartis sur {len(groupes)} groupes MS6")
print(pd.Series({g: len(v) for g, v in groupes.items()}, name="élèves").to_string())
'''))

    c.append(md(r'''
## 2. La matrice, construite **une seule fois**

C'est le point le plus important du protocole. Les deux approches liront **exactement les mêmes
nombres** : l'approche A extrait ses sous-matrices de la matrice globale par indexation, elle ne
refait aucun appel OSRM.

### La limite de `/table`, et comment on la contourne

OSRM plafonne `/table` à **100 coordonnées par requête** (au-delà : `400 Bad Request`). Or
`osrm_client.matrice` de MS5 fait **un seul appel** — ce qui lui suffit en production, où une tournée
compte au plus une cinquantaine d'arrêts, mais qui casse ici dès 3 groupes. Pire : le repli sur le
vol d'oiseau est **silencieux**, et comparer deux solveurs sur une matrice à vol d'oiseau ne prouve
rien sur le terrain.

On reprend donc le mécanisme de **MS6** (`ms6-clustering/osrm_client.py`) : la matrice est assemblée
**par blocs de 50×50**, chaque requête n'envoyant que l'union de deux blocs (≤ 100 coordonnées) avec
des index `sources`/`destinations` locaux.

> ⚠️ Une différence avec MS6 : **on ne symétrise pas**. MS6 fait `D = (D + Dᵀ)/2` parce qu'il lui faut
> une distance métrique pour ses k-médoïdes. Ici, l'asymétrie du réseau routier (sens uniques,
> tourne-à-gauche interdits) est précisément ce qui fait le coût réel d'une tournée — c'est l'argument
> de `verify_sens.py`. La lisser fausserait les deux approches à la fois.
'''))
    c.append(code(r'''
import httpx
from osrm_client import haversine_m

BLOC = 50

async def matrice_blocs(pts):
    """Matrices (durées_s, distances_m) n×n via /table, assemblées par blocs de 50×50.

    Non symétrisée : l'asymétrie du réseau est une information, pas un bruit.
    Les paires injoignables sont comblées au vol d'oiseau (et signalées).
    """
    n = len(pts)
    blocs = [list(range(i, min(i + BLOC, n))) for i in range(0, n, BLOC)]
    dur = [[None] * n for _ in range(n)]
    dist = [[None] * n for _ in range(n)]
    sem = asyncio.Semaphore(4)

    async with httpx.AsyncClient(timeout=120.0) as client:
        async def fetch(bi, bj):
            idx = bi + bj
            coords = ";".join(f"{pts[k][1]},{pts[k][0]}" for k in idx)
            s = ";".join(str(i) for i in range(len(bi)))
            d = ";".join(str(i) for i in range(len(bi), len(idx)))
            url = (f"{settings.osrm_url}/table/v1/driving/{coords}"
                   f"?annotations=duration,distance&sources={s}&destinations={d}")
            async with sem:
                r = await client.get(url)
            r.raise_for_status()
            j = r.json()
            for a, gi in enumerate(bi):
                for b, gj in enumerate(bj):
                    dur[gi][gj] = j["durations"][a][b]
                    dist[gi][gj] = j["distances"][a][b]

        await asyncio.gather(*(fetch(bi, bj) for bi in blocs for bj in blocs))

    trous = 0
    for i in range(n):
        for j in range(n):
            if dur[i][j] is None or dist[i][j] is None or dur[i][j] < 0 or dist[i][j] < 0:
                trous += 1
                d = haversine_m(pts[i], pts[j]) * 1.4
                dist[i][j] = d
                dur[i][j] = d / (30 * 1000 / 3600)
    if trous:
        print(f"  ⚠ {trous} paires injoignables comblées au vol d'oiseau")
    return dur, dist


async def construire_perimetre(n_groupes: int):
    """(ids_groupes, élèves ordonnés, durées, distances) sur une matrice UNIQUE école + élèves."""
    ids = list(groupes)[:n_groupes]
    ens = [e for g in ids for e in groupes[g]]
    pts = [ECOLE] + [(e["latitude"], e["longitude"]) for e in ens]
    dur, dist = await matrice_blocs(pts)
    return ids, ens, dur, dist


# Contrôle : la matrice est-elle bien du VRAI routier ? Le vol d'oiseau produit une
# symétrie parfaite ; OSRM, non.
ids, ens, dur, dist = await construire_perimetre(len(groupes))
asym = sum(1 for i in range(1, 20) for j in range(1, 20) if abs(dur[i][j] - dur[j][i]) > 1)
print(f"{len(ens)} élèves · matrice {len(dur)}×{len(dur)} · "
      f"{asym} paires asymétriques sur 361 testées → {'OSRM réel' if asym else '⚠ repli'}")
maxi = len(groupes)
'''))

    c.append(md(r'''
## 3. Les deux approches, sur la même instance
'''))
    c.append(code(r'''
def approche_A(ids, ens, dur, dist, budget_s):
    """MS6 + TSP : sous-matrices extraites de la matrice globale (aucun nouvel appel OSRM)."""
    routes_glob, t_total = [], 0.0
    for g in ids:
        idx = [0] + [i + 1 for i, e in enumerate(ens) if e["groupeId"] == g]
        sub = [[dur[a][b] for b in idx] for a in idx]
        order, t = chronometre(solve_tsp, sub, 0, budget_s)
        t_total += t
        routes_glob.append([idx[i] for i in order])   # réindexation vers le global
    return routes_glob, t_total


def approche_B(ids, ens, dur, dist, budget_s):
    """CVRP global : k véhicules, capacité 50, une seule résolution."""
    (routes, ok), t = chronometre(
        solve_cvrp, dur, n_vehicules=len(ids), capacite=CAPACITE,
        depot=0, time_limit_s=budget_s)
    return (routes if ok else None), t


def mesurer(nom, routes, dur, dist, t_solve):
    ch = [c for c in charges(routes) if c > 0]
    return {"approche": nom,
            "duree_min": cout_routes(routes, dur) / 60,
            "distance_km": cout_routes(routes, dist) / 1000,
            "bus_utilises": bus_utilises(routes),
            "charge_min": min(ch) if ch else 0,
            "charge_max": max(ch) if ch else 0,
            "ecart_type_charge": float(np.std(ch)) if ch else 0.0,
            "temps_resolution_s": round(t_solve, 2)}
'''))

    c.append(md(r'''
## 4. Exécution — l'écart grandit-il avec la taille de l'instance ?
'''))
    c.append(code(r'''
lignes, detail = [], {}
for k in range(2, maxi + 1):
    ids, ens, dur, dist = await construire_perimetre(k)
    budget_A = BUDGET_PAR_BUS_S                 # par bus
    budget_B = BUDGET_PAR_BUS_S * len(ids)      # même effort total

    rA, tA = await asyncio.to_thread(approche_A, ids, ens, dur, dist, budget_A)
    rB, tB = await asyncio.to_thread(approche_B, ids, ens, dur, dist, budget_B)

    mA = mesurer("MS6 + TSP", rA, dur, dist, tA)
    mB = mesurer("CVRP global", rB, dur, dist, tB) if rB else None
    for m in (mA, mB):
        if m:
            m["groupes"], m["eleves"] = k, len(ens)
            lignes.append(m)
    detail[k] = (ids, ens, dur, dist, rA, rB)

    if mB:
        ecart = (mA["duree_min"] - mB["duree_min"]) / mA["duree_min"] * 100
        gagnant = "CVRP" if ecart > 0 else "découpage MS6"
        print(f"  {k} groupes ({len(ens)} élèves) : A={mA['duree_min']:.1f} min | "
              f"B={mB['duree_min']:.1f} min | écart {ecart:+.1f} % en faveur du {gagnant}")
    else:
        print(f"  {k} groupes : le CVRP n'a pas trouvé de solution en {budget_B} s "
              f"— résultat en soi, à consigner tel quel")

tab = pd.DataFrame(lignes)[["groupes", "eleves", "approche", "duree_min", "distance_km",
                            "bus_utilises", "charge_min", "charge_max",
                            "ecart_type_charge", "temps_resolution_s"]]
tab.round(2)
'''))

    c.append(md(r'''
## 5. Contrôle de cohérence

L'approche A doit retrouver l'ordre de grandeur déjà mesuré en production. Sur le **groupe 1** des
données v2, `/api/planification/tournee?groupeId=1` donne **~17,24 km / ~36,0 min**.

> Attention à ne pas surinterpréter un écart de quelques pour cent : `solve_tsp` utilise
> `GUIDED_LOCAL_SEARCH` **borné en temps** (5 s). Ce n'est pas un algorithme déterministe à budget
> fixé — deux exécutions sur la même machine, sous des charges différentes, explorent un nombre
> d'itérations différent et peuvent rendre deux tournées voisines mais distinctes. Un écart de
> **±3 %** est du bruit de solveur ; un écart de 20 % signalerait un vrai problème (matrice ou
> affectation changée).
'''))
    c.append(code(r'''
idx1 = [0] + [i + 1 for i, e in enumerate(ens) if e["groupeId"] == ids[0]]
sub_d = [[dist[a][b] for b in idx1] for a in idx1]
sub_t = [[dur[a][b] for b in idx1] for a in idx1]
o = solve_tsp(sub_t, 0, BUDGET_PAR_BUS_S)
km, mn = cout_tournee(o, sub_d) / 1000, cout_tournee(o, sub_t) / 60
print(f"Groupe {ids[0]} ({len(idx1)-1} élèves) : {km:.2f} km | {mn:.2f} min")
print(f"Référence production        : ~17.24 km | ~36.0 min")
print(f"Écart                       : {(km-17.24)/17.24*100:+.1f} % en distance, "
      f"{(mn-36.0)/36.0*100:+.1f} % en durée")
'''))

    c.append(md(r'''
## 6. Lecture des résultats
'''))
    c.append(code(r'''
piv = tab.pivot(index="groupes", columns="approche", values="duree_min")
fig, ax = plt.subplots(1, 3, figsize=(15, 4.5))

piv.plot(kind="bar", ax=ax[0], color=["#DD8452", "#4C72B0"], rot=0)
ax[0].set_title("Durée totale de la flotte"); ax[0].set_ylabel("minutes")
ax[0].set_xlabel("nombre de groupes comparés")

if "CVRP global" in piv:
    ecart = (piv["MS6 + TSP"] - piv["CVRP global"]) / piv["MS6 + TSP"] * 100
    ax[1].plot(ecart.index, ecart.values, "-o", color="#55A868", lw=2)
    ax[1].axhline(0, color="k", lw=1)
    ax[1].set_title("Écart en faveur du CVRP"); ax[1].set_ylabel("%")
    ax[1].set_xlabel("nombre de groupes comparés")

tab.pivot(index="groupes", columns="approche", values="temps_resolution_s").plot(
    kind="bar", ax=ax[2], color=["#DD8452", "#4C72B0"], rot=0)
ax[2].set_title("Temps de résolution"); ax[2].set_ylabel("secondes")
ax[2].set_xlabel("nombre de groupes comparés")

plt.tight_layout(); plt.savefig(f"{FIG}/06_cvrp_vs_ms6_tsp.png", bbox_inches="tight"); plt.show()
'''))

    c.append(md(r'''
## 7. Équilibrage des charges

Une métrique que la seule distance masque : le CVRP peut gagner quelques pour cent en **déséquilibrant**
les bus (un à 50 élèves, un à 12). En exploitation c'est un mauvais échange — le temps à bord des
enfants du bus chargé explose, ce qui est précisément ce que le projet cherche à réduire.
'''))
    c.append(code(r'''
k_max = int(tab["groupes"].max())
ids, ens, dur, dist, rA, rB = detail[k_max]
cA = [c for c in charges(rA) if c > 0]
cB = [c for c in charges(rB) if c > 0] if rB else []

fig, ax = plt.subplots(figsize=(9, 4.5))
n = max(len(cA), len(cB)); x = np.arange(n); l = 0.35
ax.bar(x - l/2, cA + [0]*(n-len(cA)), l, label="MS6 + TSP", color="#DD8452")
if cB:
    ax.bar(x + l/2, cB + [0]*(n-len(cB)), l, label="CVRP global", color="#4C72B0")
ax.axhline(CAPACITE, color="#C44E52", ls="--", lw=1.5, label=f"capacité ({CAPACITE})")
ax.set_title(f"Charge par bus — {k_max} groupes, {len(ens)} élèves")
ax.set_xlabel("bus"); ax.set_ylabel("élèves"); ax.legend()
plt.tight_layout(); plt.savefig(f"{FIG}/06_equilibrage_charges.png", bbox_inches="tight"); plt.show()

print(tab[tab.groupes == k_max][["approche", "charge_min", "charge_max",
                                 "ecart_type_charge"]].to_string(index=False))
'''))

    c.append(md(r'''
## 8. Conclusion — mesurée sur les 300 élèves

### 8.1 En durée de conduite : la décomposition ne coûte rien

| Groupes | Élèves | MS6 + TSP | CVRP global | Écart |
|--:|--:|--:|--:|:--|
| 2 | 79 | 59,4 min | 59,2 min | +0,2 % CVRP |
| 3 | 129 | 74,3 min | 76,0 min | −2,3 % **MS6** |
| 4 | 165 | 100,2 min | 100,9 min | −0,7 % **MS6** |
| 5 | 215 | 135,8 min | 137,7 min | −1,4 % **MS6** |
| 6 | 257 | 164,1 min | 163,9 min | +0,1 % CVRP |
| 7 | **300** | **207,1 min** | **208,0 min** | **−0,4 % MS6** |

À budget de calcul égalisé, **le CVRP ne bat jamais la décomposition de plus de 0,2 %**, et lui est
le plus souvent inférieur (jusqu'à −2,3 %). Le résultat attendu — « résoudre les deux décisions
ensemble doit faire mieux » — **n'est pas au rendez-vous**.

**Pourquoi.** MS6 n'est pas un découpage arbitraire que le CVRP pourrait facilement battre : ses
k-médoïdes travaillent **déjà sur la distance routière OSRM**. L'information géographique est donc
injectée *avant* le routage. Le CVRP, lui, doit la redécouvrir seul, sur un espace de recherche
bien plus vaste (affectation × routage) et dans le même budget de temps. La décomposition n'est pas
une approximation subie : c'est une **façon d'injecter de la connaissance du domaine dans le
solveur**, et elle est payante.

### 8.2 En revanche, le CVRP trouve autre chose : un bus de moins

Sur les 7 groupes, avec 7 véhicules **disponibles**, il n'en utilise que **6** — chargés à
**50/50 exactement** (écart-type des charges : **0,00**), contre 7 bus chargés de 29 à 50 pour MS6
(écart-type **7,49**).

> **Un bus économisé, donc un chauffeur, pour +0,4 % de temps de conduite.**

Ce n'est pas une erreur de MS6, c'est un **arbitrage différent**. Le minimum théorique est
⌈300 / 50⌉ = 6 bus ; MS6 en choisit 7 parce que sa courbe de Pareto privilégie la **compacité
géographique**. Ce 7ᵉ bus achète deux choses que le tableau de durées ne montre pas :

* des tournées plus compactes, donc moins de temps à bord pour les enfants ;
* de la **marge** — le CVRP à 6 bus pleins n'en a aucune : **un élève de plus rend l'instance
  infaisable**, alors qu'une inscription en cours d'année est le cas normal dans une école.

### 8.3 Et le coût de calcul ne se lit pas dans le tableau

Les temps de résolution sont identiques **par construction** (budget égalisé). Mais l'approche A est
faite de **k TSP indépendants**, donc parallélisable : c'est exactement ce que fait
`POST /api/planification/tournees` avec `asyncio.gather` (43 s → 9 s mesuré). Un CVRP de 300 arrêts
ne se découpe pas — son budget est incompressible.

### 8.4 Verdict

**On garde MS6 + TSP.** Non par confort d'architecture, mais parce que c'est ce que dit la mesure :
la décomposition ne coûte rien en conduite, se parallélise, et laisse de la marge de capacité.

Le CVRP reste utile comme **outil de dimensionnement de flotte** : c'est lui qui répond à « combien
de bus me faut-il au minimum ? », question à laquelle MS6 ne répond pas puisqu'il optimise la
compacité. Une piste : le relancer avec `cout_fixe_vehicule` élevé pour explorer le compromis
« flotte minimale ↔ temps à bord ».

> Quel que soit le verdict, il est **mesuré**. C'est la différence entre « j'ai choisi de décomposer »
> et « j'ai comparé deux formulations du même problème, et je sais laquelle gagne, de combien, et à
> quel prix ».
'''))

    nb.cells = c
    return nb


def main():
    for nom, fabrique in (("05_vrp_study.ipynb", notebook_05),
                          ("06_cvrp_benchmark.ipynb", notebook_06)):
        path = os.path.join(HERE, nom)
        with open(path, "w", encoding="utf-8") as f:
            nbf.write(fabrique(), f)
        print("écrit :", path)


if __name__ == "__main__":
    main()
