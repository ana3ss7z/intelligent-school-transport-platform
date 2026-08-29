"""Génère les figures MS12 ajoutées au mémoire (garde, significativité, ablation).

LECTURE SEULE sur les artefacts : ce script ne fait que `json.load` /
`pd.read_csv` sur `data/ablation/resultats.json`, `data/benchmark_summary.json`
et `data/eta_dataset.csv`, puis écrit des PNG/PDF dans `notebooks/figures/`.
Il n'appelle jamais `train.main()` : `eta_model.pkl` et `eta_config.json`
restent intacts.

    cd ms12-prediction && python notebooks/gen_figures_memoire.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from viz_memoire import (ACCENT, NEUTRE, PAL6, finish, legende, note, pied,
                         save, setup, titre)

DATA = Path(__file__).resolve().parent.parent / "data"
ABL = json.loads((DATA / "ablation" / "resultats.json").read_text(encoding="utf-8"))
BENCH = json.loads((DATA / "benchmark_summary.json").read_text(encoding="utf-8"))
CFG = json.loads((DATA / "eta_config.json").read_text(encoding="utf-8"))

JOLI = {
    "facteur_contexte": "facteur_contexte\n(production)",
    "modele_extrapole": "modèle extrapolé\nhors domaine",
    "osrm_brut": "OSRM brut\n(baseline métier)",
}


# ── 1 — la garde anti-extrapolation : le mode qui tourne vraiment ───────────
def fig_garde():
    setup()
    g = ABL["garde"]["normaux"]
    ordre = ["facteur_contexte", "modele_extrapole", "osrm_brut"]
    metriques = [("MAE", "MAE (min)"), ("RMSE", "RMSE (min)"),
                 ("R2", "R²"), ("MAPE_%", "MAPE (%)")]

    fig, axes = plt.subplots(1, 4, figsize=(15, 5), dpi=150)
    for ax, (cle, label), lettre in zip(axes, metriques, "abcd"):
        vals = [g[d][cle] for d in ordre]
        coul = [PAL6[5], NEUTRE, ACCENT]
        ax.bar(range(3), vals, color=coul, width=0.62)
        for i, v in enumerate(vals):
            dec = 0.02 * (max(vals) - min(min(vals), 0))
            ax.text(i, v + (dec if v >= 0 else -dec), f"{v:.2f}", ha="center",
                    va="bottom" if v >= 0 else "top", color="dimgrey",
                    fontsize=10.5, weight="semibold")
        if min(vals) < 0:
            ax.axhline(0, color="dimgrey", linewidth=0.9)
        ax.margins(y=0.17)  # place pour l'étiquette sous une barre négative
        ax.set_xticks(range(3), ["prod.", "extrap.", "OSRM"])
        ax.set_title(r"$\bf(" + lettre + r")$" + f"  {label}", loc="left",
                     fontsize=11.5, pad=8)
    axes[0].set_ylabel("Erreur sur trajets entiers", fontsize=11)

    fig.suptitle("La garde anti-extrapolation, mesurée sur le régime de production "
                 f"({g['n']} trajets normaux de 6,4 à 11,8 km)",
                 fontsize=13, y=1.04, color="dimgrey")
    finish(*axes, grid_axis="y")
    fig.tight_layout()
    pied(fig,
         "Le modèle est entraîné sur des TRONÇONS de 0,7 à 4 km, mais les applications demandent l'ETA de la tournée restante : 6 à 12 km.\n"
         "`predire_minutes` bascule alors sur `facteur_contexte` — on interroge le modèle sur un tronçon de référence avec le contexte réel\n"
         "du moment, et on applique le facteur d'inflation obtenu à la durée OSRM restante. Le modèle ne quitte jamais son domaine.\n"
         "Résultat : −37 % d'erreur contre l'extrapolation directe, −77 % contre OSRM brut, dont le R² négatif signifie qu'il fait pire que\n"
         "prédire la moyenne. La décision la plus subtile du projet était la seule sans preuve ; elle en a une.")
    save(fig, "12_1_garde_anti_extrapolation")
    return fig


# ── 2 — le gagnant tient-il à 2,7 secondes ? ────────────────────────────────
def fig_significativite():
    setup()
    s = ABL["significativite"]
    comp = s["comparaisons"]
    ordre = sorted(comp, key=lambda k: comp[k]["delta_MAE"])
    y = np.arange(len(ordre))
    delta = [comp[k]["delta_MAE"] for k in ordre]
    bas = [comp[k]["IC95_bas"] for k in ordre]
    haut = [comp[k]["IC95_haut"] for k in ordre]
    err = [np.array(delta) - np.array(bas), np.array(haut) - np.array(delta)]

    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=150)
    ax.axvline(0, color=ACCENT, linewidth=1.6, zorder=1)
    ax.errorbar(delta, y, xerr=err, fmt="o", markersize=9, capsize=5,
                color=PAL6[5], ecolor=NEUTRE, elinewidth=2, capthick=2, zorder=3)
    for i, k in enumerate(ordre):
        ax.text(haut[i] + 0.03, i, f"+{delta[i]:.4f}", va="center",
                color="dimgrey", fontsize=9.5, weight="semibold")
    ax.set_yticks(y, [k.replace("_", " ") for k in ordre])
    ax.set_xlabel("Δ MAE par rapport à ElasticNet (minutes) — bootstrap apparié, 5 000 tirages",
                  fontsize=11.5)
    ax.set_xlim(-0.06, max(haut) * 1.22)
    ax.invert_yaxis()
    titre(ax, "ElasticNet bat significativement les dix challengers",
          f"Champion : {s['champion']} · MAE {s['MAE'][s['champion']]:.4f} min")
    finish(ax, grid_axis="x")
    pied(fig,
         "Le trait rouge marque l'égalité avec le champion : un intervalle qui le franchirait signalerait un écart non significatif.\n"
         "ElasticNet l'emporte sur Ridge de 0,045 minute — 2,7 secondes — sur 720 points. Sans intervalle de confiance, ce classement\n"
         "n'était pas défendable. Le bootstrap est APPARIÉ (mêmes indices pour les deux modèles) : c'est l'appariement qui donne la\n"
         "puissance, puisque les erreurs sont fortement corrélées d'un modèle à l'autre. Les dix intervalles sont entièrement positifs.\n"
         "Note d'honnêteté : nous attendions l'inverse. L'écart ressemble à du bruit, mais il est systématique et non aléatoire —\n"
         "la mesure a corrigé notre intuition, ce qui est exactement son rôle.")
    save(fig, "12_2_significativite_bootstrap")
    return fig


# ── 3 — et si les arbres étaient simplement mal réglés ? ────────────────────
def fig_reglage():
    setup()
    r = ABL["reglage_arbres"]
    modeles = ["xgboost", "random_forest"]
    defaut = [ABL["significativite"]["MAE"][m] for m in modeles]
    regle = [r[m]["MAE_test"] for m in modeles]
    ref = r["elasticnet_reference"]["MAE_test"]

    x = np.arange(len(modeles))
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    ax.bar(x - 0.19, defaut, 0.38, color=NEUTRE, label="Hyperparamètres par défaut")
    ax.bar(x + 0.19, regle, 0.38, color=PAL6[5], hatch="//", edgecolor="white",
           linewidth=0.7, label="Après RandomizedSearchCV (TimeSeriesSplit)")
    for xi, (d, rg) in enumerate(zip(defaut, regle)):
        ax.text(xi - 0.19, d + 0.015, f"{d:.4f}", ha="center", color="dimgrey",
                fontsize=10, weight="semibold")
        ax.text(xi + 0.19, rg + 0.015, f"{rg:.4f}", ha="center", color="dimgrey",
                fontsize=10, weight="semibold")
        ax.text(xi, rg / 2, f"−{(d - rg) / d * 100:.0f} %", ha="center",
                color="white", fontsize=12, weight="bold")
    ax.axhline(ref, color=ACCENT, linestyle="--", linewidth=1.8, zorder=3)
    note(ax, 1.42, ref + 0.012, f"ElasticNet — {ref:.4f} min", color=ACCENT, fontsize=10.5)
    ax.set_xticks(x, ["XGBoost", "Random Forest"])
    ax.set_ylabel("MAE de test (minutes, tous trajets)", fontsize=12)
    ax.set_ylim(0, max(defaut) * 1.18)
    titre(ax, "Le réglage réduit l'écart — il ne le comble pas",
          "Validation temporelle (TimeSeriesSplit à 3 replis), jamais aléatoire : on n'entraîne pas sur le futur")
    legende(ax, loc="upper right", fontsize=10)
    finish(ax, grid_axis="y")
    pied(fig,
         "C'était l'objection sérieuse : les onze candidats tournaient avec leurs hyperparamètres par défaut. Le réglage fait gagner 17 %\n"
         "à XGBoost — l'objection était donc légitime — mais il reste derrière. La conclusion « le linéaire gagne » survit à un protocole\n"
         "équitable. ElasticNet, lui, n'a rien à régler.")
    save(fig, "12_3_reglage_arbres")
    return fig


# ── 4 — la baseline que le jury demandera ───────────────────────────────────
def fig_baseline_historique():
    setup()
    bh = ABL["baseline_historique"]["normaux"]
    elastic = ABL["biais"]["avant"]["normaux"]
    osrm = next(b for b in BENCH if b["modele"] == "baseline_osrm")["eval"]["normaux"]

    noms = ["ElasticNet\n(modèle)", "Moyenne historique\npar (circuit, moment, tronçon)",
            "OSRM brut"]
    mae = [elastic["MAE"], bh["MAE"], osrm["MAE"]]
    r2 = [elastic["R2"], bh["R2"], osrm["R2"]]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
    coul = [PAL6[5], PAL6[2], NEUTRE]
    ax1.bar(range(3), mae, color=coul, width=0.6)
    for i, v in enumerate(mae):
        ax1.text(i, v + 0.04, f"{v:.3f}", ha="center", color="dimgrey",
                 fontsize=11, weight="semibold")
    # gain d'ElasticNet contre chaque baseline, écrit AU-DESSUS de la baseline
    # concernée : plus lisible qu'une flèche qui traverse les barres
    for ref in (1, 2):
        gain = (mae[ref] - mae[0]) / mae[ref] * 100
        ax1.text(ref, mae[ref] + 0.17, f"le modèle fait −{gain:.0f} %",
                 ha="center", color=ACCENT, fontsize=11, weight="bold")
    ax1.set_xticks(range(3), noms)
    ax1.set_ylabel("MAE (minutes, trajets normaux)", fontsize=12)
    ax1.set_ylim(0, max(mae) * 1.35)
    ax1.set_title(r"$\bf{(a)}$" + "  Erreur moyenne", loc="left", fontsize=12, pad=9)

    ax2.bar(range(3), r2, color=coul, width=0.6)
    for i, v in enumerate(r2):
        ax2.text(i, v + (0.02 if v >= 0 else -0.02), f"{v:.3f}", ha="center",
                 va="bottom" if v >= 0 else "top", color="dimgrey",
                 fontsize=11, weight="semibold")
    ax2.axhline(0, color="dimgrey", linewidth=0.9)
    ax2.set_xticks(range(3), noms)
    ax2.set_ylabel("R² (trajets normaux)", fontsize=12)
    ax2.set_title(r"$\bf{(b)}$" + "  Part de variance expliquée", loc="left",
                  fontsize=12, pad=9)

    fig.suptitle("Le gain réel du ML est de 44 %, pas de 52,7 %",
                 fontsize=13.5, y=1.03, color="dimgrey")
    finish(ax1, ax2, grid_axis="y")
    fig.tight_layout()
    pied(fig,
         "Le dossier compare le modèle à OSRM brut. Mais la vraie baseline d'un exploitant, c'est « ce qu'a duré ce tronçon les jours\n"
         "précédents » — un tableur suffit. Cette moyenne existait déjà comme FEATURE (`duree_moyenne_historique_s`), jamais comme\n"
         "prédicteur autonome. Le chiffre de 52,7 % publié est exact, mais il est mesuré contre la plus faible des deux baselines.\n"
         "Annoncer 44 % contre la moyenne historique est un argument plus fort, parce que c'est la comparaison qu'un jury ferait.")
    save(fig, "12_4_baseline_historique")
    return fig


# ── 5 — un gain de 15 % laissé sur la table ─────────────────────────────────
def fig_biais():
    setup()
    b = ABL["biais"]
    corr = b["correction_estimee_sur_train_min"]
    vues = [("normaux", "Trajets normaux"), ("tous", "Tous trajets (incidents compris)")]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
    x = np.arange(len(vues))

    for ax, cle, label, lettre in [(ax1, "MAE", "MAE (minutes)", "a"),
                                   (ax2, "biais", "Biais moyen (minutes)", "b")]:
        av = [b["avant"][v][cle] for v, _ in vues]
        ap = [b["apres"][v][cle] for v, _ in vues]
        ax.bar(x - 0.19, av, 0.38, color=NEUTRE, label="Avant correction")
        ax.bar(x + 0.19, ap, 0.38, color=PAL6[5], hatch="//", edgecolor="white",
               linewidth=0.7, label="Après correction")
        for xi, (a, p) in enumerate(zip(av, ap)):
            for pos, v in ((xi - 0.19, a), (xi + 0.19, p)):
                ax.text(pos, v + (0.02 if v >= 0 else -0.02), f"{v:+.3f}" if cle == "biais" else f"{v:.3f}",
                        ha="center", va="bottom" if v >= 0 else "top",
                        color="dimgrey", fontsize=10, weight="semibold")
        if min(min(av), min(ap)) < 0:
            ax.axhline(0, color="dimgrey", linewidth=0.9)
        ax.set_xticks(x, [n for _, n in vues])
        ax.set_ylabel(label, fontsize=12)
        ax.set_title(r"$\bf(" + lettre + r")$" + f"  {label.split(' (')[0]}",
                     loc="left", fontsize=12, pad=9)
    legende(ax1, loc="upper left", fontsize=10)
    gain = (b["avant"]["normaux"]["MAE"] - b["apres"]["normaux"]["MAE"]) / b["avant"]["normaux"]["MAE"] * 100
    ax1.text(0, b["apres"]["normaux"]["MAE"] / 2, f"−{gain:.1f} %", ha="center",
             color="white", fontsize=13, weight="bold")

    fig.suptitle(f"Les deux tiers de l'erreur moyenne sont un décalage constant de {corr:.3f} min",
                 fontsize=13.5, y=1.03, color="dimgrey")
    finish(ax1, ax2, grid_axis="y")
    fig.tight_layout()
    pied(fig,
         "Le notebook affichait « résidu normaux : moyenne = 0,550 » sans le commenter. Or le MAE des trajets normaux vaut 0,859 :\n"
         "les deux tiers de l'erreur sont donc corrigeables par une soustraction. La correction est estimée SUR LE TRAIN uniquement —\n"
         "la calibrer sur le test serait tricher.\n"
         "Attention au revers, et il est instructif : sur TOUS les trajets, le biais passe de +0,07 à −0,44. La sur-prédiction moyenne sur les\n"
         "trajets normaux COMPENSAIT la sous-prédiction massive des incidents. Corriger l'une découvre l'autre : c'est un arbitrage, pas un\n"
         "correctif gratuit — raison de plus pour le décider explicitement plutôt que de le subir.")
    save(fig, "12_5_correction_biais")
    return fig


# ── 6 — l'ablation : ce que le modèle PERDRAIT ──────────────────────────────
def fig_ablation_familles():
    setup()
    lignes = [r for r in ABL["ablation_familles"] if r["variante"] != "modele complet"]
    lignes.sort(key=lambda r: r["delta_normaux"])
    noms = [r["variante"].replace("sans ", "").replace("_", " ") for r in lignes]
    delta = [r["delta_normaux"] for r in lignes]
    nfeat = [r["n_features"] for r in lignes]
    complet = next(r for r in ABL["ablation_familles"] if r["variante"] == "modele complet")

    y = np.arange(len(lignes))
    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=150)
    coul = [PAL6[4] if d < 0 else (ACCENT if d > 0.3 else NEUTRE) for d in delta]
    ax.barh(y, delta, color=coul, height=0.6)
    ax.axvline(0, color="dimgrey", linewidth=1.1, zorder=3)
    for i, (d, nf) in enumerate(zip(delta, nfeat)):
        ax.text(d + (0.012 if d >= 0 else -0.012), i, f"{d:+.4f}",
                va="center", ha="left" if d >= 0 else "right",
                color="dimgrey", fontsize=10.5, weight="semibold")
    ax.set_yticks(y, [f"sans {n}" for n in noms])
    ax.set_xlabel("Δ MAE sur les trajets normaux, après réentraînement (minutes)", fontsize=11.5)
    ax.set_xlim(min(delta) - 0.09, max(delta) * 1.22)
    titre(ax, "Ce que le modèle perdrait — et les deux familles qui lui nuisent",
          f"Modèle complet : {complet['n_features']} variables, MAE {complet['MAE_normaux']:.4f} min · "
          "chaque variante est RÉENTRAÎNÉE sans sa famille")
    # les deux repères de sens vivent sous l'axe, de part et d'autre du zéro
    note(ax, -0.012, -0.55, "← retirer AMÉLIORE", ha="right",
         color=PAL6[5], fontsize=10.5)
    note(ax, 0.012, -0.55, "retirer DÉGRADE →", color=ACCENT, fontsize=10.5)
    finish(ax, grid_axis="x")
    pied(fig,
         "Les « importances » publiées sont des |coefficients| standardisés : elles disent ce que le modèle UTILISE, pas ce qu'il PERDRAIT.\n"
         "Météo et trafic portent l'essentiel — les retirer dégrade le MAE de 55 %. Les variables de contexte marocain (ramadan, jour de souk)\n"
         "valent +0,10 min, soit 12 % du MAE : ce n'est pas un ornement, et la question viendra.\n"
         "Deux familles sont inutiles, voire nuisibles : retirer le `dwell` AMÉLIORE le modèle (−0,021) et retirer le `temporel` aussi (−0,006).\n"
         "Le modèle pourrait perdre 10 de ses 26 variables et faire légèrement mieux. Et `duree_moyenne_historique_s`, 7ᵉ importance publiée\n"
         "(coefficient 0,333), ne vaut que 0,003 en ablation : la démonstration la plus nette que l'importance et l'ablation diffèrent.")
    save(fig, "12_6_ablation_familles")
    return fig


# ── 7 — le coût de calcul face à la précision ───────────────────────────────
def fig_cout_precision():
    setup()
    pts = [b for b in BENCH if not b.get("baseline")]
    fig, ax = plt.subplots(figsize=(10.5, 6.5), dpi=150)
    for b in pts:
        gagnant = b["modele"] == CFG["algorithme"]
        ax.scatter(b["fit_s"], b["eval"]["normaux"]["MAE"],
                   s=210 if gagnant else 110,
                   color=ACCENT if gagnant else PAL6[3],
                   marker="*" if gagnant else "o",
                   zorder=3 if gagnant else 2,
                   edgecolors="white", linewidths=0.8)
        ax.annotate(b["modele"].replace("_", " "), (b["fit_s"], b["eval"]["normaux"]["MAE"]),
                    textcoords="offset points", xytext=(9, 5), fontsize=9.5,
                    color=ACCENT if gagnant else "dimgrey",
                    weight="semibold" if gagnant else "normal")
    ax.set_xscale("log")
    ax.set_xlabel("Temps d'entraînement (s, échelle logarithmique)", fontsize=12)
    ax.set_ylabel("MAE sur trajets normaux (minutes)", fontsize=12)
    titre(ax, "Le gagnant est aussi le moins coûteux — ce n'est pas toujours le cas",
          "★ = modèle gelé en production")
    finish(ax, grid_axis="y", cadre=True)
    pied(fig,
         "Le temps d'entraînement fait partie du verdict : un modèle qu'on ne peut pas réentraîner en exploitation n'est pas un candidat\n"
         "crédible. Ici les deux critères s'accordent — ElasticNet est à la fois le plus précis et le plus rapide de trois ordres de grandeur.\n"
         "Cette convergence n'était pas acquise : c'est elle qui rend le choix confortable.")
    save(fig, "12_7_cout_vs_precision")
    return fig


# ── 8 — le régime d'entrée : domaine d'entraînement vs production ───────────
def fig_domaine():
    setup()
    dom = ABL["garde"]["domaine"]["distance_routiere_m"]
    df = pd.read_csv(DATA / "eta_dataset.csv")
    troncons = df["distance_routiere_m"] / 1000
    trajets = (df.groupby(["date", "moment", "circuit_id"])["distance_routiere_m"]
                 .sum() / 1000)

    fig, ax = plt.subplots(figsize=(11, 6), dpi=150)
    ax.hist(troncons, bins=40, color=PAL6[3], alpha=0.85,
            label=f"Tronçons — ce sur quoi le modèle est entraîné (n={len(troncons)})")
    ax.hist(trajets, bins=40, color=ACCENT, alpha=0.85,
            label=f"Tournées entières — ce que les applications demandent (n={len(trajets)})")
    ax.axvspan(dom["min"] / 1000, dom["max"] / 1000, color=PAL6[0], alpha=0.16, zorder=0)
    note(ax, (dom["min"] + dom["max"]) / 2000, ax.get_ylim()[1] * 0.93,
         "domaine d'entraînement", ha="center", fontsize=10.5, style="italic")
    ax.set_xlabel("Distance routière (km)", fontsize=12)
    ax.set_ylabel("Nombre d'observations", fontsize=12)
    titre(ax, "Pourquoi une garde était nécessaire : deux régimes qui ne se recouvrent pas",
          f"Domaine gelé : {dom['min'] / 1000:.2f} à {dom['max'] / 1000:.2f} km "
          f"(médiane {dom['median'] / 1000:.2f} km)")
    legende(ax, loc="upper right", fontsize=10)
    finish(ax, grid_axis="y", cadre=True)
    pied(fig,
         "Un trajet entier EST la concaténation de ses tronçons : sa distance est leur somme, sa durée réelle aussi. En agrégeant le dataset\n"
         "par (date, moment, circuit), on obtient une vérité terrain dans le régime de production — sans rien régénérer. Les deux distributions\n"
         "sont disjointes : demander au modèle une tournée de 12 km, c'est lui demander trois fois au-delà de ce qu'il a vu.\n"
         "Cette figure montre aussi, sans le vouloir, la LIMITE du générateur : les barres sont des pics parce qu'il n'existe que 12 valeurs\n"
         "distinctes de `duree_base_s`. Un modèle linéaire sur variables indicatrices retrouve donc presque exactement la formule\n"
         "multiplicative qui a produit ces données — la victoire d'ElasticNet est en partie inscrite dans le générateur. Le protocole reste\n"
         "valide, mais la généralisation à des durées GPS réelles n'est pas testée. Mieux vaut le déclarer soi-même.\n"
         "⚠️ `domaine_entrainement` vaut `null` dans `eta_config.json` : l'artefact gelé est antérieur à la garde, qui retombe donc sur une\n"
         "relecture du CSV au démarrage. Si ce fichier manque au déploiement, `hors_domaine` devient toujours faux et le service extrapole\n"
         "EN SILENCE — exactement ce que la garde existe pour empêcher. Ces bornes devraient être gelées dans le JSON.")
    save(fig, "12_8_domaine_entrainement")
    return fig


FIGURES_MEMOIRE = [
    fig_garde, fig_significativite, fig_reglage, fig_baseline_historique,
    fig_biais, fig_ablation_familles, fig_cout_precision, fig_domaine,
]

if __name__ == "__main__":
    for f in FIGURES_MEMOIRE:
        plt.close(f())
    print(f"\n{len(FIGURES_MEMOIRE)} figures MS12 générées.")
