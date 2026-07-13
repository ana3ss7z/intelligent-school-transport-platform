"""
Preuve numérique (sur OSRM RÉEL) que le SOIR doit garder le MÊME ordre que le matin, pas l'inverse.

N'a besoin que d'OSRM (docker osrm_meknes, port 5000) — pas de MS2/MS5.
On prend un groupe réel d'élèves de Meknès, on résout le TSP matin (OR-Tools + durées OSRM),
puis on compare le TEMPS À BORD par élève pour :
  - soir « même ordre » (recommandé)      : école → e1 → e2 → … → en → école
  - soir « ordre inversé » (code d'avant)  : école → en → … → e2 → e1 → école
La distance/durée TOTALE est identique (même cycle) ; seule l'équité du temps à bord change.

Usage : python verify_sens.py
"""
import asyncio
import csv
import os
import statistics

from osrm_client import matrice
from vrp import solve_tsp, cout_tournee
from config import settings

CSV = os.path.join(os.path.dirname(__file__), "..", "ms6-clustering", "data", "eleves_meknes.csv")
ECOLE = (settings.ecole_lat, settings.ecole_lng)


def charger_groupe(secteur_cible: str, n_max: int = 14) -> list[dict]:
    """Un 'bus' réaliste = élèves d'un même secteur (groupe compact), limité à n_max."""
    out = []
    with open(CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["secteur"] == secteur_cible:
                out.append({"id": int(r["id"]), "nom": r["nom"],
                            "latitude": float(r["latitude"]), "longitude": float(r["longitude"])})
    return out[:n_max]


def temps_a_bord(order: list[int], M: list[list[float]], mode: str) -> dict[int, float]:
    """Temps (s) passé dans le bus par nœud-élève, selon le mode.
    order = [0, i1, …, in, 0] (0 = école = dépôt).
    - ramassage : l'élève monte quand on l'atteint et reste jusqu'à l'école (fin) ;
    - depose    : l'élève est à bord depuis l'école (début) jusqu'à ce qu'on le dépose."""
    res = {}
    for t in range(1, len(order) - 1):        # positions des élèves (hors dépôt)
        node = order[t]
        if mode == "ramassage":
            res[node] = cout_tournee(order[t:], M)      # de l'élève jusqu'à la fin (école)
        else:  # depose
            res[node] = cout_tournee(order[:t + 1], M)  # de l'école (début) jusqu'à l'élève
    return res


async def main():
    groupe = charger_groupe("Sidi Baba", n_max=14)
    if len(groupe) < 4:
        groupe = charger_groupe("Médina Nord", n_max=14)
    noms = {i + 1: e["nom"] for i, e in enumerate(groupe)}   # node index -> nom
    pts = [ECOLE] + [(e["latitude"], e["longitude"]) for e in groupe]
    print(f"Groupe réel : {len(groupe)} élèves | école (dépôt) = {ECOLE}")

    dur, dist = await matrice(pts)

    # Contrôle « vraies routes » : la matrice OSRM est-elle asymétrique ?
    n = len(pts)
    asym = max(abs(dur[i][j] - dur[j][i]) for i in range(n) for j in range(n))
    src = "OSRM réel (asymétrique)" if asym > 1e-6 else "symétrique (repli haversine ? OSRM down)"
    print(f"Matrice durées : {n}x{n} | asymétrie max = {asym:.1f} s -> {src}\n")

    # TSP matin (ordre optimal)
    order = solve_tsp(dur, depot=0, time_limit_s=settings.vrp_time_limit_s)
    rev = [0] + [i for i in order if i != 0][::-1] + [0]     # cycle inversé

    # Distances/durées TOTALES (doivent être ~identiques : même cycle)
    print("== Coût TOTAL de la tournée (opérateur) ==")
    print(f"  matin / soir même-ordre : {cout_tournee(order, dist)/1000:6.2f} km | {cout_tournee(order, dur)/60:5.1f} min")
    print(f"  soir ordre inversé      : {cout_tournee(rev, dist)/1000:6.2f} km | {cout_tournee(rev, dur)/60:5.1f} min\n")

    # Temps à bord par élève
    matin = temps_a_bord(order, dur, "ramassage")            # ramassage sur l'ordre matin
    soir_meme = temps_a_bord(order, dur, "depose")           # dépose sur le MÊME ordre
    soir_inv = temps_a_bord(rev, dur, "depose")              # dépose sur l'ordre INVERSÉ

    print("== Temps À BORD par élève (minutes) ==")
    print(f"{'élève':<14}{'matin':>7}{'soir=même':>11}{'TOTAL même':>12}{'soir=inv':>10}{'TOTAL inv':>11}")
    tot_meme, tot_inv = [], []
    for node in [i for i in order if i != 0]:
        m = matin[node] / 60
        sm = soir_meme[node] / 60
        si = soir_inv[node] / 60
        tot_meme.append(m + sm); tot_inv.append(m + si)
        print(f"{noms[node]:<14}{m:>7.1f}{sm:>11.1f}{m+sm:>12.1f}{si:>10.1f}{m+si:>11.1f}")

    def stats(v):
        return f"max={max(v):5.1f}  moy={statistics.mean(v):5.1f}  écart-type={statistics.pstdev(v):5.2f}"

    print("\n== Équité du temps à bord sur la journée (matin + soir) ==")
    print(f"  MÊME ordre (recommandé) : {stats(tot_meme)}")
    print(f"  ordre INVERSÉ (avant)   : {stats(tot_inv)}")
    gain_max = max(tot_inv) - max(tot_meme)
    print(f"\n=> 'Même ordre' réduit le pire temps à bord de {gain_max:.1f} min "
          f"et l'écart-type de {statistics.pstdev(tot_inv)-statistics.pstdev(tot_meme):.2f}.")
    if asym > 1e-6:
        print("   De plus, sur cette matrice OSRM ASYMÉTRIQUE, l'ordre inversé (non ré-optimisé) coûte AUSSI")
        print("   plus cher à l'opérateur (voir coût total ci-dessus) — il est donc doublement mauvais.")
    print("   Conclusion : le SOIR doit garder le MÊME ordre que le matin (plus équitable, coût <= inversé).")


if __name__ == "__main__":
    asyncio.run(main())
