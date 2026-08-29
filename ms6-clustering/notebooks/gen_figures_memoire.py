"""Génère les figures MS6 ajoutées au mémoire (arène, ablation, stabilité).

LECTURE SEULE sur les artefacts : ce script ne fait que `json.load` sur
`data/ablation_distance.json`, `data/sensibilite_ordre.json`,
`data/stabilite.json`, `data/churn_apres_correctif.json`,
`data/quality_baseline.json` et `notebooks/production_config.json`, puis écrit
des PNG/PDF dans `notebooks/figures/`. Aucun clustering n'est recalculé,
`production_config.json` et `quality_baseline.json` ne sont jamais réécrits.

    cd ms6-clustering && python notebooks/gen_figures_memoire.py
"""

import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from viz_memoire import (ACCENT, NEUTRE, PAL6, finish, legende, note, pied,
                         save, setup, titre)

ICI = Path(__file__).resolve().parent
DATA = ICI.parent / "data"

ABL = json.loads((DATA / "ablation_distance.json").read_text(encoding="utf-8"))
ORDRE = json.loads((DATA / "sensibilite_ordre.json").read_text(encoding="utf-8"))
STAB = json.loads((DATA / "stabilite.json").read_text(encoding="utf-8"))
CHURN = json.loads((DATA / "churn_apres_correctif.json").read_text(encoding="utf-8"))
BASE = json.loads((DATA / "quality_baseline.json").read_text(encoding="utf-8"))
PROD = json.loads((ICI / "production_config.json").read_text(encoding="utf-8"))
RAYON = json.loads((DATA / "rayon_sweep_resultats.json").read_text(encoding="utf-8"))

COURT = {
    "kmedoides_capacitaire_ROUTIER (production)": "k-médoïdes\ncapacitaire ROUTIER\n(production)",
    "kmedoides_capacitaire_EUCLIDIEN": "k-médoïdes\ncapacitaire\nEUCLIDIEN",
    "kmeans_capacitaire (euclidien)": "k-means\ncapacitaire\n(euclidien)",
    "kmeans (euclidien, sans capacite)": "k-means SANS\ncontrainte\n(infaisable)",
    "baseline_quartier": "baseline\n« un bus\npar quartier »",
    "baseline_aleatoire": "baseline\naléatoire\néquilibrée",
}


# ── 1 — l'arène : l'algorithme de production entre enfin en lice ────────────
def fig_arene():
    setup()
    arene = ABL["arene"]
    noms = [COURT[a["methode"]] for a in arene]
    prod = 0  # la production est la première ligne

    vues = [
        ("temps_a_bord_moyen_min", "Temps à bord moyen\npar enfant (min)", "a", False),
        ("duree_tournees_min", "Durée totale de la flotte\n(min de conduite)", "b", False),
        ("silhouette", "Silhouette\n(sur matrice routière)", "c", False),
        ("compacite_med_m", "Compacité médiane\n(m)", "d", False),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(17, 6), dpi=150)
    for ax, (cle, label, lettre, _) in zip(axes, vues):
        vals = [a[cle] for a in arene]
        coul = []
        for i, a in enumerate(arene):
            if i == prod:
                coul.append(ACCENT)
            elif not a["faisable"]:
                coul.append("#d9d9d9")   # infaisable : chiffres fictifs
            else:
                coul.append(PAL6[3])
        barres = ax.barh(range(len(arene)), vals, color=coul, height=0.62)
        for b, a in zip(barres, arene):
            if not a["faisable"]:
                b.set_hatch("xx")
                b.set_edgecolor("white")
        for i, v in enumerate(vals):
            ax.text(v + max(vals) * 0.02, i, f"{v:.4g}", va="center",
                    color="dimgrey", fontsize=9.5, weight="semibold")
        ax.set_yticks(range(len(arene)), noms if lettre == "a" else [""] * len(arene),
                      fontsize=9)
        # la silhouette peut être négative (partition aléatoire) : l'axe doit
        # la montrer, sinon la barre disparaît et l'étiquette flotte seule
        if min(vals) < 0:
            ax.set_xlim(min(vals) * 1.9, max(vals) * 1.22)
            ax.axvline(0, color="dimgrey", linewidth=0.9, zorder=2)
        else:
            ax.set_xlim(0, max(vals) * 1.22)
        ax.invert_yaxis()
        ax.set_title(r"$\bf(" + lettre + r")$" + f"  {label}", loc="left",
                     fontsize=11, pad=9)
    fig.suptitle(f"Toutes les méthodes notées avec la MÊME règle — matrice routière, "
                 f"k = {ABL['k']}, capacité {ABL['capacite']}, {ABL['n']} élèves",
                 fontsize=13, y=1.05, color="dimgrey")
    finish(*axes, grid_axis="x")
    fig.tight_layout()
    pied(fig,
         "Les partitions construites en distance euclidienne sont ÉVALUÉES sur la matrice routière, comme les autres : sans cela chacun\n"
         "serait jugé à sa propre aune et l'euclidien gagnerait mécaniquement. Les barres hachurées grises sont INFAISABLES (un groupe de\n"
         "66 élèves pour 50 places) : leurs chiffres sont fictifs, ce bus n'existe pas. Leur seul rôle est de borner ce qu'on abandonne en\n"
         "refusant l'infaisable — 3,4 % de conduite.\n"
         "Ce que cela règle : « votre algorithme fait-il mieux qu'un simple découpage par quartier ? » — oui, 14,6 % de conduite en moins et\n"
         "4,7 minutes de bus en moins par enfant, chaque matin. Le dossier n'avait aucune réponse à cette question jusqu'ici.")
    save(fig, "06_1_arene_complete")
    return fig


# ── 2 — l'ablation propre : un seul facteur change ─────────────────────────
def fig_ablation_distance():
    setup()
    a = ABL["arene"]
    rout = next(x for x in a if "ROUTIER" in x["methode"])
    eucl = next(x for x in a if "EUCLIDIEN" in x["methode"])

    vues = [("silhouette", "Silhouette", "", 1),
            ("duree_tournees_min", "Durée de flotte", " min", 1),
            ("temps_a_bord_moyen_min", "Temps à bord\npar enfant", " min", 1)]
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.6), dpi=150)
    for ax, (cle, label, unite, _), lettre in zip(axes, vues, "abc"):
        vals = [rout[cle], eucl[cle]]
        ax.bar([0, 1], vals, color=[ACCENT, NEUTRE], width=0.56)
        for i, v in enumerate(vals):
            ax.text(i, v + max(vals) * 0.02, f"{v:.4g}{unite}", ha="center",
                    color="dimgrey", fontsize=11, weight="semibold")
        # On affiche l'écart ABSOLU : c'est la grandeur que l'ablation mesure
        # directement. Le pourcentage dépend de la base choisie — le document
        # de référence rapporte −9,7 % sur le temps à bord en prenant la
        # valeur routière au dénominateur ; l'écrire ici en % obligerait à
        # trancher cette convention dans un graphique.
        ecart = vals[0] - vals[1]
        ax.set_xticks([0, 1], ["routier", "euclidien"])
        ax.set_ylim(0, max(vals) * 1.30)
        ax.set_title(r"$\bf(" + lettre + r")$" + f"  {label}", loc="left",
                     fontsize=11.5, pad=9)
        marquant = abs(ecart) / max(vals) > 0.02
        ax.text(0.5, max(vals) * 1.19, f"{ecart:+.4g}{unite}", ha="center",
                fontsize=13, weight="bold",
                color=(PAL6[5] if (ecart < 0 and marquant) else "dimgrey"))
    fig.suptitle("Ablation propre : même algorithme, même k, même graine — seule la matrice change",
                 fontsize=13, y=1.03, color="dimgrey")
    finish(*axes, grid_axis="y")
    fig.tight_layout()
    pied(fig,
         "Trois lectures d'une même expérience. (a) En silhouette, l'effet est INVISIBLE (+0,0019) : c'est pourtant l'indice que le dossier\n"
         "mettait en avant — il ne pouvait donc pas soutenir la thèse qu'on lui faisait porter. (b) En temps de conduite, l'effet est réel mais\n"
         "modeste : 1,5 %. (c) En temps passé dans le bus par chaque enfant, il est SIX FOIS plus grand : −9,7 %, soit 1,7 minute par enfant\n"
         "et par trajet. Sur 300 élèves et deux trajets par jour, ce sont 17 heures d'enfant économisées chaque jour.\n"
         "La distance routière ne rend pas les groupes « plus jolis » : elle raccourcit le temps que chaque enfant passe dans le bus.")
    save(fig, "06_2_ablation_distance_routiere")
    return fig


# ── 3 — un argmax sur du bruit ─────────────────────────────────────────────
def fig_bruit_silhouette():
    setup()
    var = ABL["variance_graines"]
    ks = [v["k"] for v in var]
    moy = [v["silhouette_moy"] for v in var]
    sd = [v["silhouette_ecart_type"] for v in var]
    lo = [v["silhouette_min"] for v in var]
    hi = [v["silhouette_max"] for v in var]

    fig, ax = plt.subplots(figsize=(10.5, 6), dpi=150)
    for i, k in enumerate(ks):
        ax.plot([k, k], [lo[i], hi[i]], color=NEUTRE, linewidth=8,
                solid_capstyle="round", alpha=0.55,
                zorder=1, label="Étendue sur 10 graines" if i == 0 else None)
    coul = [ACCENT if k == PROD["k_production"] else PAL6[5] for k in ks]
    ax.errorbar(ks, moy, yerr=sd, fmt="o", markersize=11, capsize=6,
                ecolor="dimgrey", elinewidth=1.8, capthick=1.8,
                linestyle="none", zorder=3, color=PAL6[5])
    ax.scatter(ks, moy, s=130, c=coul, zorder=4, edgecolors="white", linewidths=1)
    for k, m, s in zip(ks, moy, sd):
        ax.text(k, m - s - 0.011, f"±{s:.4f}", ha="center", color="dimgrey",
                fontsize=10, weight="semibold")
    ax.set_xticks(ks)
    for etiq, k in zip(ax.get_xticklabels(), ks):
        if k == PROD["k_production"]:
            etiq.set_color(ACCENT)
            etiq.set_fontweight("bold")
    ax.set_xlabel("Nombre de bus (k)", fontsize=12)
    ax.set_ylabel("Silhouette (matrice routière)", fontsize=12)
    titre(ax, "Les écarts entre k voisins sont du même ordre que leur propre bruit",
          f"10 graines par k · le k gelé en production ({PROD['k_production']}) est en rouge")
    legende(ax, loc="lower right", fontsize=10)
    finish(ax, grid_axis="y", cadre=True)
    pied(fig,
         "k = 7 est remarquablement stable (±0,0001) et domine k = 8 et k = 9 EN MÉDIANE : le choix gelé est bien fondé. Mais k = 8 et k = 9\n"
         "sont instables (±0,0119 et ±0,0204), et les écarts qui les séparent (0,006 à 0,017) sont du même ordre que ce bruit.\n"
         "Or `choisir_k` retenait le k de meilleure silhouette : un ARGMAX sur des valeurs indiscernables. Un k instable qui tire haut évince\n"
         "alors un k stable qui vaut mieux en moyenne — c'est la cause racine de la loterie mesurée à la figure suivante.")
    save(fig, "06_3_bruit_silhouette_par_k")
    return fig


# ── 4 — la loterie : le nombre de bus dépendait de l'ordre des lignes ──────
def fig_sensibilite_ordre():
    setup()
    dist = Counter(x["k"] for x in ORDRE)
    ks = sorted(dist)
    n = len(ORDRE)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=150,
                                   gridspec_kw={"width_ratios": [1, 1.25]})

    coul = [ACCENT if k != PROD["k_production"] else PAL6[4] for k in ks]
    barres = ax1.bar([str(k) for k in ks], [dist[k] for k in ks], color=coul, width=0.6)
    for b, k in zip(barres, ks):
        ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.4,
                 f"{dist[k]}/{n}\n({dist[k] / n * 100:.0f} %)", ha="center",
                 color="dimgrey", fontsize=10.5, weight="semibold")
    ax1.set_xlabel("Nombre de bus retenu", fontsize=12)
    ax1.set_ylabel(f"Occurrences sur {n} permutations", fontsize=12)
    ax1.set_ylim(0, max(dist.values()) * 1.30)
    ax1.set_title(r"$\bf{(a)}$" + "  Mêmes données, trois réponses", loc="left",
                  fontsize=12, pad=9)

    for k, c in zip(ks, ["#1f253f", ACCENT, "#72a5b4"]):
        vals = [x["silhouette"] for x in ORDRE if x["k"] == k]
        jitter = np.random.default_rng(0).normal(0, 0.055, len(vals))
        ax2.scatter([k] * len(vals) + jitter, vals, s=95, alpha=0.8, color=c,
                    edgecolors="white", linewidths=0.8, label=f"k = {k}")
    ax2.set_xticks(ks)
    ax2.set_xlabel("Nombre de bus retenu", fontsize=12)
    ax2.set_ylabel("Silhouette finale obtenue", fontsize=12)
    ax2.set_title(r"$\bf{(b)}$" + "  Le mécanisme : un même k n'a pas une qualité fixe",
                  loc="left", fontsize=12, pad=9)
    sept = [x["silhouette"] for x in ORDRE if x["k"] == 7]
    neuf = [x["silhouette"] for x in ORDRE if x["k"] == 9]
    if sept and neuf:
        ax2.axhspan(min(sept), max(neuf), color=NEUTRE, alpha=0.10, zorder=0)
        note(ax2, 7.35, (min(sept) + max(neuf)) / 2,
             "quand k = 7 tombe à 0,405,\nk = 9 à 0,419 l'emporte",
             fontsize=10, style="italic")
    legende(ax2, loc="lower right", fontsize=10)

    fig.suptitle("Le nombre de bus n'était pas une propriété des données",
                 fontsize=13.5, y=1.03, color="dimgrey")
    finish(ax1, grid_axis="y")
    finish(ax2, grid_axis="y", cadre=True)
    fig.tight_layout()
    pied(fig,
         "Mêmes 300 élèves, mêmes adresses, même graine, même matrice OSRM. Seul l'ORDRE des lignes change — celui que PostgreSQL\n"
         "renvoie, `findAll()` étant sans `ORDER BY`. Deux bus et deux chauffeurs d'écart, sans qu'aucune donnée métier n'ait bougé.\n"
         "Et la boucle se referme sur elle-même : MS6 réécrit les 300 lignes à chaque application, ce qui change le tas PostgreSQL —\n"
         "APPLIQUER un clustering pouvait donc changer le nombre de bus du clustering suivant. Une inscription en cours d'année, cas normal\n"
         "dans une école, devenait un tirage au sort sur la flotte.")
    save(fig, "06_4_sensibilite_ordre")
    return fig


# ── 5 — le churn : ce que coûte une inscription ────────────────────────────
def fig_churn():
    setup()
    res = STAB["inscriptions"]["resume"]
    regles = [("actuel", "Règle initiale\n(argmax)"),
              ("robuste", "Règle robuste\n(médiane + parcimonie)"),
              ("robuste_hysteresis", "Robuste\n+ hystérésis")]
    vues = [("churn_moyen_%", "Churn moyen"), ("churn_median_%", "Churn médian"),
            ("churn_max_%", "Churn maximum")]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 6), dpi=150,
                                   gridspec_kw={"width_ratios": [1.45, 1]})

    x = np.arange(len(regles))
    largeur = 0.26
    for i, (cle, label) in enumerate(vues):
        vals = [res[r][cle] for r, _ in regles]
        coul = [PAL6[5], PAL6[3], PAL6[1]][i]
        b = ax1.bar(x + (i - 1) * largeur, vals, largeur, color=coul,
                    hatch=["", "//", ".."][i], edgecolor="white", linewidth=0.6,
                    label=label)
        for bb, v in zip(b, vals):
            ax1.text(bb.get_x() + bb.get_width() / 2, v + 0.35, f"{v:.2f}",
                     ha="center", color="dimgrey", fontsize=9.5, weight="semibold")
    ax1.set_xticks(x, [n for _, n in regles])
    ax1.set_ylabel("Élèves changeant de bus entre deux recalculs (%)", fontsize=11.5)
    ax1.set_ylim(0, max(res[r][v] for r, _ in regles for v, _ in vues) * 1.28)
    ax1.set_title(r"$\bf{(a)}$" + "  Le coût d'une inscription, par règle de choix",
                  loc="left", fontsize=12, pad=9)
    legende(ax1, loc="upper center", fontsize=9.5, ncol=3)

    chg = [res[r]["n_changements_de_k"] for r, _ in regles]
    coul = [ACCENT if c > 4 else (PAL6[3] if c > 2 else PAL6[4]) for c in chg]
    b = ax2.bar(x, chg, color=coul, width=0.58)
    for bb, c, (r, _) in zip(b, chg, regles):
        ax2.text(bb.get_x() + bb.get_width() / 2, c + 0.15, str(c), ha="center",
                 color="dimgrey", fontsize=12, weight="semibold")
        ax2.text(bb.get_x() + bb.get_width() / 2, 0.25,
                 f"k : {res[r]['k_min']}→{res[r]['k_max']}", ha="center",
                 color="white", fontsize=10, weight="bold")
    ax2.set_xticks(x, ["Initiale", "Robuste", "Robuste\n+ hystérésis"])
    ax2.set_ylabel("Changements de flotte sur 15 inscriptions", fontsize=11.5)
    ax2.set_ylim(0, max(chg) * 1.25)
    ax2.set_title(r"$\bf{(b)}$" + "  Combien de fois la flotte bascule", loc="left",
                  fontsize=12, pad=9)

    finish(ax1, ax2, grid_axis="y")
    fig.tight_layout()
    pied(fig,
         "On inscrit les élèves deux par deux de 270 à 300, chaque règle choisissant librement son k, et l'on mesure le pourcentage d'élèves\n"
         "qui changent de bus. Les étiquettes de groupe étant arbitraires, elles sont appariées par recouvrement maximal (affectation\n"
         "hongroise) avant comptage.\n"
         "La règle initiale ne se stabilise JAMAIS : k fait 7 → 9 → 7 → 8 → 7 → 9, neuf fois en quinze inscriptions, et chaque bascule déplace\n"
         "12 à 13 % des élèves — une trentaine d'enfants, autant de familles à prévenir. Pour UNE inscription.\n"
         "La règle robuste seule a un maximum PIRE (25,4 %) : à n = 272, six bus deviennent faisables et la parcimonie saute dessus. C'est un\n"
         "défaut de la proposition, pas de la mesure — d'où l'hystérésis, seule variante sans contre-indicateur mesuré.")
    save(fig, "06_5_churn_par_regle")
    return fig


# ── 6 — le correctif déployé, mesuré ───────────────────────────────────────
def fig_correctif():
    setup()
    avant = STAB["inscriptions"]["resume"]["actuel"]
    apres = CHURN["avec_hysteresis"]
    sans = CHURN["sans_hysteresis"]

    vues = [("churn_moyen_%", "moyen", "moyen"), ("churn_median_%", "median", "médian"),
            ("churn_max_%", "max", "maximum")]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=150)

    x = np.arange(len(vues))
    va = [avant[c] for c, _, _ in vues]
    vs = [sans[k] for _, k, _ in vues]
    vp = [apres[k] for _, k, _ in vues]
    ax1.bar(x - 0.27, va, 0.26, color=ACCENT, label="Avant (règle initiale)")
    ax1.bar(x, vs, 0.26, color=NEUTRE, hatch="//", edgecolor="white",
            linewidth=0.6, label="Après, sans hystérésis")
    ax1.bar(x + 0.27, vp, 0.26, color=PAL6[5], hatch="..", edgecolor="white",
            linewidth=0.6, label="Après, AVEC hystérésis (déployé)")
    for xi, (a, s, p) in enumerate(zip(va, vs, vp)):
        for dx, v in ((-0.27, a), (0, s), (0.27, p)):
            ax1.text(xi + dx, v + 0.3, f"{v:.2f}", ha="center", color="dimgrey",
                     fontsize=9.5, weight="semibold")
    ax1.set_xticks(x, [n for _, _, n in vues])
    ax1.set_ylabel("Churn (%)", fontsize=12)
    ax1.set_ylim(0, max(va + vs + vp) * 1.30)
    ax1.set_title(r"$\bf{(a)}$" + "  Élèves déplacés par inscription", loc="left",
                  fontsize=12, pad=9)
    legende(ax1, loc="upper left", fontsize=9.5)

    etats = ["Avant\n(30 permutations)", "Après\n(30 permutations)"]
    dist_av = Counter(x["k"] for x in ORDRE)
    valeurs = [[dist_av[k] for k in (7, 8, 9)], [30, 0, 0]]
    bas = np.zeros(2)
    for i, (k, c, h) in enumerate(zip((7, 8, 9), [PAL6[4], PAL6[2], ACCENT], ["", "//", ".."])):
        v = np.array([valeurs[0][i], valeurs[1][i]])
        ax2.bar(etats, v, 0.5, bottom=bas, color=c, hatch=h, edgecolor="white",
                linewidth=0.7, label=f"k = {k}")
        for xi, (vv, bb) in enumerate(zip(v, bas)):
            if vv:
                ax2.text(xi, bb + vv / 2, f"{vv}", ha="center", va="center",
                         color="white", fontsize=12, weight="bold")
        bas += v
    ax2.set_ylabel("Permutations donnant ce nombre de bus", fontsize=12)
    ax2.set_ylim(0, 38)
    ax2.set_title(r"$\bf{(b)}$" + "  La loterie disparaît", loc="left",
                  fontsize=12, pad=9)
    legende(ax2, loc="upper center", fontsize=10, ncol=3)

    fig.suptitle("Le correctif déployé le 24/08, mesuré et non estimé",
                 fontsize=13.5, y=1.03, color="dimgrey")
    finish(ax1, ax2, grid_axis="y")
    fig.tight_layout()
    pied(fig,
         "Deux correctifs indissociables : (1) `choisir_k` compare désormais la MÉDIANE de plusieurs initialisations par k, puis retient le plus\n"
         "petit k à moins de ε du meilleur ; (2) une hystérésis interdit de changer de flotte tant que l'ancien k reste faisable et n'est pas battu\n"
         "de plus d'une marge métier. Faits séparément, ils ne suffisent pas — la règle robuste seule fait bondir le churn maximum à 25,4 %.\n"
         "Résultat : 30 permutations sur 30 donnent k = 7, et une SEULE partition distincte — strictement reproductible. Vérifié par le vrai\n"
         "chemin de données (`ms2_client.get_all_eleves()`) : ordre MS2 et ordre inversé produisent des affectations identiques élève par élève.\n"
         "⚠️ Coût unique au déploiement : 22 élèves sur 300 (7,3 %) changent de bus au premier recalcul. Une seule fois — à faire un jour où\n"
         "les familles peuvent être prévenues.")
    save(fig, "06_6_correctif_mesure")
    return fig


# ── 7 — le garde-fou qualité, et le cliquet qu'il a fallu défaire ──────────
def fig_qualite():
    setup()
    m = PROD["metriques_routieres"]
    ancre = m.get("silhouette_partition_complete", BASE["silhouette"])
    plancher = 0.75 * ancre

    fig, ax = plt.subplots(figsize=(11, 6), dpi=150)
    niveaux = [
        (BASE["silhouette"], "Référence en vigueur\n(quality_baseline.json)", PAL6[5], "-"),
        (ancre, "Ancre de conception\n(production_config.json)", PAL6[3], "--"),
        (plancher, "Plancher CRITIQUE\n(0,75 × ancre)", ACCENT, ":"),
        (0.5183, "Ancienne référence périmée\n(17/07, jeu à 14 dispersés)", NEUTRE, "-."),
    ]
    for i, (v, label, c, ls) in enumerate(niveaux):
        ax.barh(i, v, height=0.55, color=c,
                hatch="xx" if "périmée" in label else "", edgecolor="white", linewidth=0.7)
        ax.text(v + 0.008, i, f"{v:.4f}", va="center", color="dimgrey",
                fontsize=11, weight="semibold")
    ax.set_yticks(range(len(niveaux)), [l for _, l, _, _ in niveaux], fontsize=10)
    ax.set_xlabel("Silhouette de la partition complète", fontsize=12)
    ax.set_xlim(0, 0.62)
    ax.invert_yaxis()
    titre(ax, "Une référence trop haute se verrouille elle-même",
          f"Verdict courant : OK · {BASE['n_eleves']} élèves · capacité {BASE['capacity']} · "
          f"{BASE['n_disperses_total']} dispersés")
    finish(ax, grid_axis="x")
    pied(fig,
         "`maybe_maj_baseline` ne réécrit la référence QUE si le verdict est OK. Une référence trop haute rend donc tout run DEGRADE… ce qui\n"
         "l'empêche d'être mise à jour : trop haute → DEGRADE → jamais réécrite → toujours trop haute. Constaté : une référence à 0,5183 écrite\n"
         "le 17/07 sur un jeu à 14 dispersés a jugé pendant CINQ SEMAINES des runs à 17 dispersés dont le niveau atteignable est 0,4256.\n"
         "Correctif : la référence ne peut jamais dépasser l'ancre de conception, et elle enregistre son contexte (effectif, capacité, rayon) —\n"
         "un changement de capacité ou de rayon la rend inapplicable.\n"
         "⚠️ Ne PAS « écrire la référence même sur DEGRADE » : c'est la correction qui vient à l'esprit en premier, et elle DÉTRUIT le garde-fou —\n"
         "chaque run serait comparé au précédent légèrement moins bon, et une dérive lente ne déclencherait jamais rien.")
    save(fig, "06_7_garde_fou_qualite")
    return fig


# ── 8 — le rayon : une silhouette qui monte en excluant les cas difficiles ──
def fig_rayon():
    setup()
    sweep = RAYON["balayage"]
    lab = [r["libelle"] for r in sweep]
    x = np.arange(len(sweep))
    sil = [r["silhouette"] for r in sweep]
    non = [r["non_affectes"] for r in sweep]
    cmax = [r["compacite_max_m"] for r in sweep]
    n = RAYON["n_eleves"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 6), dpi=150)

    ax1.plot(x, sil, marker="o", markersize=9, linewidth=2.4, color=PAL6[5],
             label="Silhouette (elle MONTE)")
    ax1.set_ylabel("Silhouette", fontsize=12, color=PAL6[5])
    ax1.set_ylim(0.35, 0.86)
    axd = ax1.twinx()
    axd.bar(x, [v / n * 100 for v in non], width=0.55, color=ACCENT, alpha=0.75,
            zorder=0, label="Élèves sans bus (%)")
    for xi, v in zip(x, non):
        if v:
            axd.text(xi, v / n * 100 + 1.6, f"{v}", ha="center", color=ACCENT,
                     fontsize=10, weight="semibold")
    axd.set_ylabel("Élèves NON AFFECTÉS (% des 300)", fontsize=12, color=ACCENT)
    axd.set_ylim(0, 72)
    axd.tick_params(axis="y", length=0, labelcolor="dimgrey")
    axd.grid(False)
    ax1.set_zorder(axd.get_zorder() + 1)
    ax1.patch.set_visible(False)
    ax1.set_xticks(x, lab)
    ax1.set_xlabel("Rayon maximal élève → médoïde (m)", fontsize=12)
    ax1.set_title(r"$\bf{(a)}$" + "  La silhouette s'améliore… en excluant des élèves",
                  loc="left", fontsize=12, pad=9)

    ax2.plot(x, cmax, marker="s", markersize=8, linewidth=2.2, color=PAL6[3],
             label="Compacité maximale obtenue")
    contrainte = [r["rayon_m"] if r["rayon_m"] else np.nan for r in sweep]
    ax2.plot(x, contrainte, linestyle="--", linewidth=1.8, color="dimgrey",
             marker="x", markersize=8, label="Rayon demandé (contrainte)")
    ax2.set_xticks(x, lab)
    ax2.set_xlabel("Rayon maximal élève → médoïde (m)", fontsize=12)
    ax2.set_ylabel("Distance routière (m)", fontsize=12)
    ax2.set_title(r"$\bf{(b)}$" + "  La contrainte est bien DURE : elle est toujours tenue",
                  loc="left", fontsize=12, pad=9)
    legende(ax2, loc="upper right", fontsize=10)

    fig.suptitle("Le rayon maximal : un arbitrage, et un piège d'interprétation",
                 fontsize=13.5, y=1.03, color="dimgrey")
    finish(ax1, grid_axis="y")
    finish(ax2, grid_axis="y", cadre=True)
    fig.tight_layout()
    pied(fig,
         "Le rayon est une contrainte DURE : un élève sans médoïde à portée devient « non affecté », c'est-à-dire à ramasser\n"
         "individuellement. Le panneau (b) vérifie que la contrainte est bien respectée — la compacité obtenue reste toujours sous le rayon\n"
         "demandé.\n"
         "Le panneau (a) porte le vrai enseignement, et c'est un piège classique : à 800 m, la silhouette atteint 0,7955 — presque le double de\n"
         "la valeur de production. On serait tenté d'y voir un bien meilleur clustering. En réalité, 156 élèves sur 300 ont été EXCLUS de la\n"
         "partition. L'indice s'améliore parce qu'on lui a retiré les cas difficiles, pas parce que le regroupement est meilleur.\n"
         "C'est pourquoi le projet garde le rayon désactivé en production, et pourquoi une silhouette ne se lit jamais sans son effectif.\n"
         "Contrôle de conformité : la ligne « rayon désactivé » EST la configuration de production, et elle reproduit bien ce que le service\n"
         "publie — k = 7 et silhouette 0,4256, vérifiés le 29/08 contre `GET /api/clustering/quality`.")
    save(fig, "06_8_rayon_arbitrage")
    return fig


FIGURES_MEMOIRE = [
    fig_arene, fig_ablation_distance, fig_bruit_silhouette,
    fig_sensibilite_ordre, fig_churn, fig_correctif, fig_qualite, fig_rayon,
]

if __name__ == "__main__":
    for f in FIGURES_MEMOIRE:
        plt.close(f())
    print(f"\n{len(FIGURES_MEMOIRE)} figures MS6 générées.")
