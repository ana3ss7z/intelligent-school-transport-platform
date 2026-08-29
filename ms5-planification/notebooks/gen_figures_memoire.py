"""Génère les figures MS5 ajoutées au mémoire (CVRP global vs MS6 + TSP).

LECTURE SEULE : ce script charge `data/cvrp_benchmark_resultats.json` et écrit
des PNG/PDF dans `notebooks/figures/`. Il ne relance aucun solveur.

Le JSON est produit par `../rejouer_cvrp.py`, qui rejoue le benchmark sur la
partition MS6 **en vigueur** (lue en direct depuis MS2). Il contient aussi la
campagne du 23/08, conservée pour montrer que la conclusion résiste au
changement de partition.

Séparer le calcul (là-bas) du tracé (ici) permet de retracer les figures sans
MS2 ni OSRM, et garantit que deux figures d'un même rapport décrivent la même
exécution.

    cd ms5-planification && python notebooks/gen_figures_memoire.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from viz_memoire import (ACCENT, NEUTRE, PAL6, finish, legende, note, pied,
                         save, setup, titre)

DATA = Path(__file__).resolve().parent.parent / "data"
RES = json.loads((DATA / "cvrp_benchmark_resultats.json").read_text(encoding="utf-8"))
LIGNES = RES["resultats"]

A, B = "MS6 + TSP", "CVRP global"


def _serie(approche, cle):
    return [r[cle] for r in LIGNES if r["approche"] == approche]


GROUPES = sorted({r["groupes"] for r in LIGNES})
ELEVES = [next(r["eleves"] for r in LIGNES if r["groupes"] == g) for g in GROUPES]


# ── 1 — l'écart ne grandit pas avec la taille de l'instance ────────────────
def fig_ecart_vs_taille():
    setup()
    da, db = _serie(A, "duree_min"), _serie(B, "duree_min")
    # On LIT les écarts calculés par le banc plutôt que de les redériver ici :
    # les durées du tableau sont arrondies à 2 décimales, et un recalcul
    # décalerait le dernier chiffre. Une figure ne doit pas contredire d'un
    # dixième le texte qu'elle illustre.
    ecart = [RES["ecarts_publies_%"][str(g)] for g in GROUPES]
    max_cvrp = max(ecart)          # meilleur gain du CVRP, en %
    max_ms6 = abs(min(ecart))      # meilleur gain de la décomposition

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 6), dpi=150,
                                   gridspec_kw={"width_ratios": [1.15, 1]})

    x = np.arange(len(GROUPES))
    ax1.bar(x - 0.19, da, 0.38, color=ACCENT, label="MS6 + TSP (décomposition)")
    ax1.bar(x + 0.19, db, 0.38, color=PAL6[3], hatch="//", edgecolor="white",
            linewidth=0.6, label="CVRP global (monolithique)")
    for xi, (a, b) in enumerate(zip(da, db)):
        ax1.text(xi - 0.19, a + 4, f"{a:.0f}", ha="center", color="dimgrey",
                 fontsize=9, weight="semibold")
        ax1.text(xi + 0.19, b + 4, f"{b:.0f}", ha="center", color="dimgrey",
                 fontsize=9, weight="semibold")
    ax1.set_xticks(x, [f"{g} bus\n{e} élèves" for g, e in zip(GROUPES, ELEVES)],
                   fontsize=9.5)
    ax1.set_ylabel("Durée totale de la flotte (min)", fontsize=12)
    ax1.set_ylim(0, max(da + db) * 1.16)
    ax1.set_title(r"$\bf{(a)}$" + "  Durée de conduite, à budget de calcul égalisé",
                  loc="left", fontsize=12, pad=9)
    legende(ax1, loc="upper left", fontsize=10)

    # Couleurs héritées du panneau (a) : une barre porte la couleur de
    # l'approche qui GAGNE, pas celle du signe. Sans cela, le rouge voudrait
    # dire « MS6+TSP » à gauche et « avantage CVRP » à droite.
    coul = [ACCENT if e < 0 else PAL6[3] for e in ecart]
    ax2.axhline(0, color="dimgrey", linewidth=1.1, zorder=2)
    ax2.bar(x, ecart, color=coul, width=0.55, zorder=3)
    for xi, e in enumerate(ecart):
        ax2.text(xi, e + (0.12 if e >= 0 else -0.12), f"{e:+.1f} %", ha="center",
                 va="bottom" if e >= 0 else "top", color="dimgrey",
                 fontsize=10, weight="semibold")
    ax2.set_xticks(x, [str(g) for g in GROUPES])
    ax2.set_xlabel("Nombre de groupes (et de bus)", fontsize=12)
    ax2.set_ylabel("Écart de durée : (MS6+TSP − CVRP) / MS6+TSP", fontsize=11.5)
    ax2.set_ylim(min(ecart) * 1.55, max(ecart) * 2.6)
    ax2.set_title(r"$\bf{(b)}$" + "  L'écart ne grandit pas avec la taille",
                  loc="left", fontsize=12, pad=9)
    note(ax2, len(GROUPES) - 0.5, max(ecart) * 1.9, "CVRP meilleur ↑",
         ha="right", color=PAL6[3], fontsize=9.5)
    note(ax2, len(GROUPES) - 0.5, min(ecart) * 1.35, "MS6 + TSP meilleur ↓",
         ha="right", color=ACCENT, fontsize=9.5)

    fig.suptitle(f"À budget égal, le CVRP ne gagne au mieux que {max_cvrp:.1f} % — "
                 f"et perd jusqu'à {max_ms6:.1f} %",
                 fontsize=13.5, y=1.03, color="dimgrey")
    finish(ax1, ax2, grid_axis="y")
    fig.tight_layout()
    pied(fig,
         "La question intéressante n'est pas « qui gagne sur 300 élèves » mais « l'écart GRANDIT-IL avec la taille ? » — c'est-à-dire : la\n"
         "décomposition se dégrade-t-elle quand le problème grossit ? Il fallait six points de mesure pour répondre, et la réponse est non :\n"
         "l'écart oscille autour de zéro sans tendance, y compris au point le plus grand.\n"
         "La théorie dit qu'un CVRP résolu À L'OPTIMUM est au moins aussi bon. Mais on ne résout pas à l'optimum : on donne 35 secondes à une\n"
         "heuristique, et en 35 secondes sur trois cents arrêts, elle ne retrouve pas ce que MS6 savait déjà. Car les k-médoïdes de MS6\n"
         "travaillent DÉJÀ sur la distance routière : l'information géographique est injectée AVANT le routage. La décomposition n'est donc pas\n"
         "une approximation qu'on subit, c'est une façon d'injecter de la connaissance du domaine dans le solveur.")
    save(fig, "05_1_ecart_vs_taille")
    return fig


# ── 2 — le résultat inattendu : un bus de moins ────────────────────────────
def fig_equilibrage():
    setup()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=150)

    x = np.arange(len(GROUPES))
    ba, bb = _serie(A, "bus_utilises"), _serie(B, "bus_utilises")
    ax1.plot(x, ba, marker="o", markersize=9, linewidth=2.2, color=ACCENT,
             label="MS6 + TSP")
    ax1.plot(x, bb, marker="s", markersize=8, linewidth=2.2, color=PAL6[3],
             linestyle="--", label="CVRP global")
    ax1.scatter([x[-1]], [bb[-1]], s=280, facecolors="none", edgecolors=PAL6[5],
                linewidths=2.4, zorder=4)
    ax1.annotate("un bus de moins", (x[-1], bb[-1]), textcoords="offset points",
                 xytext=(-16, -30), ha="right", color=PAL6[5], fontsize=11,
                 weight="semibold",
                 arrowprops=dict(arrowstyle="->", color=PAL6[5], lw=1.5))
    ax1.set_xticks(x, [str(g) for g in GROUPES])
    ax1.set_xlabel("Bus disponibles", fontsize=12)
    ax1.set_ylabel("Bus réellement utilisés", fontsize=12)
    ax1.set_ylim(1, max(ba) + 1.3)
    ax1.set_title(r"$\bf{(a)}$" + "  Le CVRP se passe du 7ᵉ bus", loc="left",
                  fontsize=12, pad=9)
    legende(ax1, loc="upper left", fontsize=10)

    sa, sb = _serie(A, "ecart_type_charge"), _serie(B, "ecart_type_charge")
    ax2.bar(x - 0.19, sa, 0.38, color=ACCENT, label="MS6 + TSP")
    ax2.bar(x + 0.19, sb, 0.38, color=PAL6[3], hatch="//", edgecolor="white",
            linewidth=0.6, label="CVRP global")
    for xi, (a, b) in enumerate(zip(sa, sb)):
        ax2.text(xi - 0.19, a + 0.22, f"{a:.1f}", ha="center", color="dimgrey",
                 fontsize=9, weight="semibold")
        ax2.text(xi + 0.19, b + 0.22, f"{b:.1f}", ha="center", color="dimgrey",
                 fontsize=9, weight="semibold")
    ax2.set_xticks(x, [str(g) for g in GROUPES])
    ax2.set_xlabel("Nombre de groupes", fontsize=12)
    ax2.set_ylabel("Écart-type de la charge des bus (élèves)", fontsize=11.5)
    ax2.set_ylim(0, max(sa + sb) * 1.22)
    ax2.set_title(r"$\bf{(b)}$" + "  … en remplissant exactement à 50/50", loc="left",
                  fontsize=12, pad=9)
    legende(ax2, loc="upper right", fontsize=10)

    fig.suptitle("Le tableau des durées cachait la découverte la plus intéressante",
                 fontsize=13.5, y=1.03, color="dimgrey")
    finish(ax1, ax2, grid_axis="y")
    fig.tight_layout()
    pied(fig,
         "Avec 7 bus disponibles, le CVRP n'en utilise que 6 — chargés à 50/50 exactement (écart-type 0,00 contre 7,49). Un bus, donc un\n"
         "chauffeur, économisé pour +0,4 % de temps de conduite.\n"
         "Ce n'est PAS une erreur de MS6, c'est un arbitrage différent. Le minimum théorique est ⌈300/50⌉ = 6 ; MS6 en choisit 7 exprès, parce\n"
         "que sa courbe de Pareto arbitre entre le nombre de bus et la COMPACITÉ des groupes. Ce septième bus achète deux choses que la\n"
         "colonne « durée » ne montre pas : des tournées plus compactes — donc moins de temps à bord pour chaque enfant — et de la MARGE.\n"
         "La solution à six bus pleins n'en a aucune : un élève de plus et l'instance devient infaisable. Or une inscription en cours d'année est\n"
         "le cas normal dans une école, pas une exception. Le CVRP n'est donc pas jeté : il devient l'outil de DIMENSIONNEMENT DE FLOTTE.")
    save(fig, "05_2_equilibrage_flotte")
    return fig


# ── 3 — le coût de calcul, et pourquoi la décomposition se parallélise ─────
def fig_cout_calcul():
    setup()
    ta = _serie(A, "temps_resolution_s")
    fig, ax = plt.subplots(figsize=(10.5, 6), dpi=150)

    x = np.array(GROUPES)
    parallele = [t / g for t, g in zip(ta, GROUPES)]
    ax.plot(x, ta, marker="o", markersize=9, linewidth=2.2, color=NEUTRE,
            label="Budget total alloué (identique aux deux approches)")
    ax.plot(x, parallele, marker="D", markersize=8, linewidth=2.2, color=PAL6[5],
            label="MS6 + TSP en parallèle : durée d'attente réelle")
    ax.fill_between(x, parallele, ta, color=PAL6[0], alpha=0.18, zorder=0)
    for g, t, p in zip(x, ta, parallele):
        ax.text(g, t + 1.1, f"{t:.0f} s", ha="center", color="dimgrey",
                fontsize=9.5, weight="semibold")
    ax.text(x[-1] - 0.15, (ta[-1] + parallele[-1]) / 2,
            "ce que la parallélisation\nrend au CVRP", ha="right", va="center",
            color=PAL6[5], fontsize=10.5, style="italic")
    ax.set_xticks(x)
    ax.set_xlabel("Nombre de groupes (et de bus)", fontsize=12)
    ax.set_ylabel("Temps de résolution (s)", fontsize=12)
    ax.set_ylim(0, max(ta) * 1.18)
    titre(ax, "Sept TSP indépendants se résolvent en parallèle — un CVRP est insécable",
          "Budget égalisé : A = k × 5 s réparti sur k solveurs · B = une seule résolution de k × 5 s")
    legende(ax, loc="upper left", fontsize=10)
    finish(ax, grid_axis="y", cadre=True)
    pied(fig,
         "Le budget égalisé est le seul découpage équitable pour comparer la QUALITÉ des solutions — mais il masque un avantage\n"
         "opérationnel de la décomposition : ses k TSP sont indépendants, donc parallélisables. C'est ce que fait déjà `/tournees` avec\n"
         "`asyncio.gather` (43 s → 9 s mesuré en production). Le CVRP, lui, est un seul bloc insécable.\n"
         "L'objection « laissez tourner le CVRP plus longtemps » est donc à double tranchant : on pourrait, et il finirait par rattraper — mais si\n"
         "l'on décide d'allouer plus de temps, l'approche décomposée en profite AUSSI, et sans attendre plus longtemps.")
    save(fig, "05_3_cout_calcul")
    return fig


# ── 4 — la réplication : la conclusion résiste au changement de partition ──
def fig_replication():
    setup()
    anc = RES["campagne_precedente"]
    groupes = sorted(int(k) for k in RES["ecarts_publies_%"])
    e_anc = [anc["ecarts_publies_%"][str(g)] for g in groupes]
    e_new = [RES["ecarts_publies_%"][str(g)] for g in groupes]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 6), dpi=150,
                                   gridspec_kw={"width_ratios": [1.35, 1]})

    x = np.arange(len(groupes))
    ax1.axhline(0, color="dimgrey", linewidth=1.1, zorder=2)
    ax1.bar(x - 0.19, e_anc, 0.38, color=NEUTRE, zorder=3,
            label=f"23/08 — partition d'alors (écart-type {anc['ecart_type_partition']})")
    ax1.bar(x + 0.19, e_new, 0.38, color=ACCENT, hatch="//", edgecolor="white",
            linewidth=0.6, zorder=3,
            label=f"29/08 — partition actuelle (écart-type {RES['ecart_type_partition']})")
    for xi, (a, b) in enumerate(zip(e_anc, e_new)):
        for dx, v in ((-0.19, a), (0.19, b)):
            ax1.text(xi + dx, v + (0.12 if v >= 0 else -0.12), f"{v:+.1f}",
                     ha="center", va="bottom" if v >= 0 else "top",
                     color="dimgrey", fontsize=9, weight="semibold")
    ax1.set_xticks(x, [str(g) for g in groupes])
    ax1.set_xlabel("Nombre de groupes (et de bus)", fontsize=12)
    ax1.set_ylabel("Écart de durée : (MS6+TSP − CVRP) / MS6+TSP", fontsize=11.5)
    ax1.set_ylim(min(e_anc + e_new) * 1.5, max(e_anc + e_new) * 2.4)
    ax1.set_title(r"$\bf{(a)}$" + "  Les deux campagnes, point par point",
                  loc="left", fontsize=12, pad=9)
    note(ax1, len(groupes) - 0.45, max(e_anc + e_new) * 1.75, "CVRP meilleur ↑",
         ha="right", color=PAL6[3], fontsize=9.5)
    note(ax1, len(groupes) - 0.45, min(e_anc + e_new) * 1.25, "MS6 + TSP meilleur ↓",
         ha="right", color=ACCENT, fontsize=9.5)
    legende(ax1, loc="upper left", fontsize=9)

    # ce qui compte vraiment : les deux conclusions structurelles tiennent-elles ?
    def bus_a_7(bloc):
        return next(r["bus_utilises"] for r in bloc
                    if r["groupes"] == 7 and r["approche"] == "CVRP global")

    def sd_a_7(bloc, approche):
        return next(r["ecart_type_charge"] for r in bloc
                    if r["groupes"] == 7 and r["approche"] == approche)

    labels = ["Bus utilisés\npar le CVRP\n(sur 7 disponibles)",
              "Écart-type des\ncharges — CVRP",
              "Écart-type des\ncharges — MS6+TSP"]
    v_anc = [bus_a_7(anc["resultats"]), sd_a_7(anc["resultats"], "CVRP global"),
             sd_a_7(anc["resultats"], "MS6 + TSP")]
    v_new = [bus_a_7(RES["resultats"]), sd_a_7(RES["resultats"], "CVRP global"),
             sd_a_7(RES["resultats"], "MS6 + TSP")]
    x2 = np.arange(len(labels))
    ax2.bar(x2 - 0.19, v_anc, 0.38, color=NEUTRE)
    ax2.bar(x2 + 0.19, v_new, 0.38, color=ACCENT, hatch="//", edgecolor="white",
            linewidth=0.6)
    for xi, (a, b) in enumerate(zip(v_anc, v_new)):
        for dx, v in ((-0.19, a), (0.19, b)):
            ax2.text(xi + dx, v + 0.18, f"{v:g}", ha="center", color="dimgrey",
                     fontsize=10, weight="semibold")
    ax2.set_xticks(x2, labels, fontsize=9.5)
    ax2.set_ylim(0, max(v_anc + v_new) * 1.28)
    ax2.set_title(r"$\bf{(b)}$" + "  Et le résultat qui compte : identique",
                  loc="left", fontsize=12, pad=9)

    fig.suptitle("Réplication sur la partition de production : la conclusion ne bouge pas",
                 fontsize=13.5, y=1.03, color="dimgrey")
    finish(ax1, ax2, grid_axis="y")
    fig.tight_layout()
    pied(fig,
         "Le benchmark du 23/08 avait tourné sur la répartition d'alors. La migration vers 7 bus du 27/08 en a produit une autre — mêmes\n"
         "7 bus et 300 élèves, mais pas les mêmes élèves dans les mêmes bus. Le rejouer était donc nécessaire : c'est la règle 7 du protocole\n"
         "du projet, « consommer la même source de données que le service ».\n"
         "(a) Les écarts point par point bougent — normal, ce sont d'autres instances. (b) Mais les deux résultats structurels sont\n"
         "IDENTIQUES : le CVRP se passe toujours du 7ᵉ bus, en remplissant à 50/50 exactement (écart-type 0,00).\n"
         "Une conclusion qui survit à un changement de données est plus solide qu'une conclusion obtenue une seule fois.")
    save(fig, "05_4_replication")
    return fig


FIGURES_MEMOIRE = [fig_ecart_vs_taille, fig_equilibrage, fig_cout_calcul, fig_replication]

if __name__ == "__main__":
    for f in FIGURES_MEMOIRE:
        plt.close(f())
    print(f"\n{len(FIGURES_MEMOIRE)} figures MS5 générées.")
