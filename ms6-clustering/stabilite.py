"""
MS6 — stabilité du nombre de bus, et ce qui se passe quand on inscrit des élèves.

Contexte
--------
Le §5 du benchmark a mesuré que le `k` retenu dépend de l'**ordre des lignes** : sur 30 permutations
des mêmes 300 élèves, k = 7 (57 %), 8 (7 %), 9 (37 %). La cause n'est pas l'ordre lui-même mais
`choisir_k`, qui prend l'**argmax** de silhouettes dont le bruit d'initialisation (±0,012 à ±0,020)
dépasse les écarts qui séparent les candidats.

Ce module ne corrige rien en production. Il **mesure deux correctifs candidats** :

**A. Une règle de choix robuste** — pour chaque `k`, médiane de la silhouette sur plusieurs
   initialisations, puis on retient le **plus petit `k` à moins de ε du meilleur** (règle de
   parcimonie, apparentée au « 1-SE rule » de la sélection de modèle). Question : cela suffit-il à
   supprimer la loterie ?

**B. L'amorçage à chaud (warm start)** — initialiser les médoïdes sur ceux du run précédent plutôt
   que sur un K-Means à froid. Question : quand un élève s'inscrit en cours d'année, combien
   d'enfants changent de bus alors que rien ne les concerne ? C'est le **churn**, et il n'a jamais
   été mesuré — alors que c'est ce que les familles subissent.

    python stabilite.py            → rapport + data/stabilite.json
"""
from __future__ import annotations

import json
import math
import os

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

import features as feat
from algorithms import affectation_capacitaire, _medoides_centraux
from evaluation import evaluer
from selection import pareto

DATA = os.path.join(os.path.dirname(__file__), "data")
CAP = 50
EPSILON = 0.02          # marge de parcimonie = ordre de grandeur du bruit mesuré sur k=8/k=9


def charger():
    df = pd.read_csv(os.path.join(DATA, "eleves_meknes.csv"))
    XY, _ = feat.projeter_metres(df[["latitude", "longitude"]].to_numpy(float))
    ROAD = np.load(os.path.join(DATA, "osrm_dist_m.npy"))
    return df["id"].to_numpy(), XY, ROAD


# ═══════════════ A. Une règle de choix robuste au bruit ══════════════════════
def choisir_k_robuste(D, XY, capacity, k_margin=3, iters=6,
                      n_init=3, epsilon=EPSILON, seeds=(0, 1, 2)):
    """Médiane de la silhouette sur `n_init` initialisations, puis plus petit `k` à moins de ε.

    Deux différences avec `selection.choisir_k` :
    - on ne juge plus un `k` sur **une** initialisation, mais sur la médiane de plusieurs — un `k`
      instable ne peut plus gagner sur un coup de chance ;
    - à qualité indiscernable (écart < ε), on préfère le **plus petit `k`**. Ce n'est pas de la
      frilosité : un bus de moins, c'est un chauffeur de moins, et l'écart n'est pas mesurable.
    """
    n = len(D)
    k_min = math.ceil(n / capacity)
    stats = []
    for k in range(k_min, k_min + k_margin + 1):
        if k * capacity < n:
            continue
        sils = []
        for s in seeds[:n_init]:
            rows = pareto(D, XY, capacity, k_min=k, k_margin=0, iters=iters)
            # `pareto` réutilise la graine interne ; on la fait varier via une permutation
            # déterministe des lignes, ce qui est exactement la source de bruit à neutraliser.
            if s:
                p = np.random.default_rng(s).permutation(n)
                r2 = pareto(D[np.ix_(p, p)], XY[p], capacity, k_min=k, k_margin=0, iters=iters)
                sils.append(r2[0]["silhouette"])
            else:
                sils.append(rows[0]["silhouette"])
        stats.append({"k": k, "silhouette_mediane": float(np.median(sils)),
                      "silhouettes": [round(x, 4) for x in sils]})
    meilleur = max(s["silhouette_mediane"] for s in stats)
    retenus = [s for s in stats if s["silhouette_mediane"] >= meilleur - epsilon]
    return min(retenus, key=lambda s: s["k"])["k"], stats


def experience_A(ids, XY, ROAD, n_perms=15) -> dict:
    """La règle robuste supprime-t-elle la loterie sur l'ordre ?"""
    n = len(ids)
    ks = []
    for s in range(n_perms):
        p = np.arange(n) if s == 0 else np.random.default_rng(100 + s).permutation(n)
        k, _ = choisir_k_robuste(ROAD[np.ix_(p, p)], XY[p], CAP)
        ks.append(k)
        print(f"  perm {s:2d} -> k={k}", flush=True)
    import collections
    return {"n_permutations": n_perms, "distribution": dict(sorted(collections.Counter(ks).items()))}


# ═══════════ B. Inscrire des élèves : churn à froid vs à chaud ═══════════════
def _kmedoides_depuis(D, XY, k, capacity, medoids_init=None, iters=6, seed=42):
    """k-médoïdes capacitaire, avec amorçage explicite possible.

    Copie fidèle de `algorithms.kmedoids_capacitaire`, à une différence près : les médoïdes de
    départ peuvent être **imposés**. C'est tout le correctif « warm start », en un paramètre.
    """
    if medoids_init is None:
        from sklearn.cluster import KMeans
        base = KMeans(n_clusters=k, random_state=seed, n_init=10).fit_predict(XY)
        medoids = _medoides_centraux(D, base, k, fallback=list(range(k)))
    else:
        medoids = list(medoids_init)
    labels = None
    for _ in range(iters):
        labels = affectation_capacitaire(D[:, medoids], capacity)
        nouveaux = _medoides_centraux(D, labels, k, fallback=medoids)
        if set(nouveaux) == set(medoids):
            break
        medoids = nouveaux
    return labels, medoids


def _churn(ids_a, lab_a, ids_b, lab_b) -> float:
    """% d'élèves communs qui changent de bus entre deux runs.

    Les étiquettes de groupe sont arbitraires (le groupe « 3 » d'un run n'est pas celui du suivant).
    On apparie donc les groupes par **recouvrement maximal** (affectation hongroise) avant de
    compter. Sans cet appariement, on mesurerait une permutation d'étiquettes, pas un vrai
    changement de bus.
    """
    ia = {e: i for i, e in enumerate(ids_a)}
    communs = [e for e in ids_b if e in ia]
    a = np.array([lab_a[ia[e]] for e in communs])
    ib = {e: i for i, e in enumerate(ids_b)}
    b = np.array([lab_b[ib[e]] for e in communs])
    ka, kb = a.max() + 1, b.max() + 1
    M = np.zeros((ka, kb), dtype=int)
    for x, y in zip(a, b):
        if x >= 0 and y >= 0:
            M[x, y] += 1
    li, co = linear_sum_assignment(-M)
    corresp = dict(zip(li, co))
    changes = sum(1 for x, y in zip(a, b) if corresp.get(x, -1) != y)
    return 100.0 * changes / max(1, len(communs))


def experience_B(ids, XY, ROAD, depart=270, pas=2) -> dict:
    """On inscrit des élèves un par un et on mesure ce que ça déplace — **avec `k` libre**.

    ⚠️ Une première version de cette expérience figeait `k = 7` pour « isoler l'effet de
    l'inscription ». C'était une erreur de conception : à `k` constant, le churn est déjà faible
    (≈ 0,5 %) et l'expérience ne testait rien. **Le churn vient du changement de `k`** — quand la
    flotte passe de 7 à 9 bus, il faut bien redistribuer tout le monde. On laisse donc chaque règle
    choisir son `k`, ce qui est le comportement réel du service.
    """
    n = len(ids)
    from selection import choisir_k
    modes = ("actuel", "robuste", "robuste_hysteresis")
    resultats = {m: [] for m in modes}
    prev = {m: None for m in modes}

    for taille in range(depart, n + 1, pas):
        idx = np.arange(taille)
        D, X, I = ROAD[np.ix_(idx, idx)], XY[idx], ids[idx]
        for mode in modes:
            if mode == "actuel":
                rows = pareto(D, X, CAP, k_min=math.ceil(taille / CAP), k_margin=3)
                best = choisir_k(rows, min_silhouette=0.50)
                k, lab, med = best["k"], best["labels"], best["medoids"]
            else:
                k, stats = choisir_k_robuste(D, X, CAP)
                if mode == "robuste_hysteresis" and prev[mode] is not None:
                    # Hystérésis : on ne change de flotte que si l'ancien `k` est devenu
                    # INFAISABLE, ou si le nouveau le bat de plus de ε. Sans cela, la règle de
                    # parcimonie court après tout `k` plus petit qui devient faisable — et chaque
                    # bascule redistribue toute l'école.
                    k_prev = prev[mode]["k"]
                    faisable = k_prev * CAP >= taille
                    dispo = {s["k"]: s["silhouette_mediane"] for s in stats}
                    if faisable and k_prev in dispo and dispo[k_prev] >= dispo[k] - EPSILON:
                        k = k_prev
                lab, med = _kmedoides_depuis(D, X, k, CAP)
            churn = (_churn(prev[mode]["ids"], prev[mode]["labels"], I, lab)
                     if prev[mode] is not None else None)
            m = evaluer(lab, CAP, D=D, medoids=med)
            resultats[mode].append({"n": taille, "k": k,
                                    "churn_%": None if churn is None else round(churn, 2),
                                    "silhouette": m["silhouette"]})
            prev[mode] = {"ids": I, "labels": lab, "medoids": med, "k": k}
        cells = []
        for m in modes:
            r = resultats[m][-1]
            c = "  -  " if r["churn_%"] is None else f"{r['churn_%']:5.1f}"
            cells.append(f"{m[:9]:>9s} k={r['k']} churn {c} %")
        print(f"  n={taille:3d}  " + " | ".join(cells), flush=True)

    resume = {}
    for mode in list(resultats):
        vals = [r["churn_%"] for r in resultats[mode] if r["churn_%"] is not None]
        ks = [r["k"] for r in resultats[mode]]
        resume[mode] = {
            "churn_moyen_%": round(float(np.mean(vals)), 2),
            "churn_median_%": round(float(np.median(vals)), 2),
            "churn_max_%": round(float(np.max(vals)), 2),
            "k_min": min(ks), "k_max": max(ks),
            "n_changements_de_k": sum(1 for x, y in zip(ks, ks[1:]) if x != y),
        }
    resultats["resume"] = resume
    return resultats


def main() -> None:
    ids, XY, ROAD = charger()
    print(f"[MS6] {len(ids)} eleves | capacite {CAP} | epsilon parcimonie = {EPSILON}\n")

    print("## A. La regle de choix robuste supprime-t-elle la loterie sur l'ordre ?\n")
    A = experience_A(ids, XY, ROAD)
    print(f"\n  distribution de k : {A['distribution']}\n")

    print("## B. Inscrire un eleve : combien d'enfants changent de bus ?\n")
    B = experience_B(ids, XY, ROAD)
    print(f"\n  regle ACTUELLE : {B['resume']['actuel']}")
    print(f"  regle ROBUSTE  : {B['resume']['robuste']}")

    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "stabilite.json"), "w", encoding="utf-8") as f:
        json.dump({"epsilon": EPSILON, "regle_robuste": A, "inscriptions": B}, f,
                  indent=2, ensure_ascii=False)
    print(f"\n[MS6] -> {os.path.join(DATA, 'stabilite.json')}")


if __name__ == "__main__":
    main()
