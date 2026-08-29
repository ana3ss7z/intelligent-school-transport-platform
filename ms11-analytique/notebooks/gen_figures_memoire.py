"""Génère les figures MS11 ajoutées au mémoire (règles live + ablation ML).

LECTURE SEULE sur les artefacts : ce script ne fait que `json.load` sur
`data/live_rules_benchmark.json` et `data/ablation_anomaly.json`, puis écrit
des PNG/PDF dans `notebooks/figures/`. Aucun modèle n'est réentraîné, aucun
artefact gelé n'est réécrit.

    cd ms11-analytique && python notebooks/gen_figures_memoire.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from viz_memoire import (ACCENT, NEUTRE, PAL6, finish, legende, note, pied,
                         save, setup, titre)

DATA = Path(__file__).resolve().parent.parent / "data"
LIVE = json.loads((DATA / "live_rules_benchmark.json").read_text(encoding="utf-8"))
ABL = json.loads((DATA / "ablation_anomaly.json").read_text(encoding="utf-8"))

SEUILS = LIVE["seuils_production"]
JOLI = {  # noms lisibles pour le mémoire
    "seuil_ratio": "Seuil ratio",
    "seuil_surprise": "Seuil surprise",
    "iforest_all": "IForest (toutes features)",
    "iforest_curated": "IForest (features curées)",
}


def _marquer(ax, valeurs, retenue):
    """Signale la valeur en production en colorant SON étiquette d'axe.

    Préféré à une flèche ou un trait vertical : une étiquette d'axe ne peut
    heurter ni une barre, ni une courbe, ni le titre de l'axe.
    """
    for etiq, v in zip(ax.get_xticklabels(), valeurs):
        if v == retenue:
            etiq.set_color(PAL6[5])
            etiq.set_fontweight("bold")


# ── A1 — la figure signature : la déviation est aveugle ─────────────────────
def fig_couverture_spatiale():
    setup()
    lignes = LIVE["couverture_spatiale_deviation"]
    detours = [r["detour_nominal_m"] for r in lignes]
    part = [r["part_parcours_detectee_%"] for r in lignes]
    median = [r["ecart_mesure_median_m"] for r in lignes]

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    ax.fill_between(detours, part, 100, color=NEUTRE, alpha=0.13, zorder=0)
    ax.plot(detours, part, marker="o", markersize=8, linewidth=2.2, color=ACCENT)

    seuil = SEUILS["deviation_m"]
    ax.axvline(seuil, color="dimgrey", linestyle="--", linewidth=1.2, zorder=0)
    note(ax, seuil + 10, 74, f"seuil de production\n{seuil:.0f} m", fontsize=9)
    note(ax, 520, 82, "angle mort de la règle", fontsize=11, style="italic")

    for x, y in zip(detours, part):
        ax.annotate(f"{y:.0f} %", (x, y), textcoords="offset points",
                    xytext=(0, -18), ha="center", color="dimgrey",
                    fontsize=9.5, weight="semibold")

    ax.set_xlabel("Détour réellement effectué par le bus (m)", fontsize=12)
    ax.set_ylabel("Part du parcours où l'alerte se déclenche (%)", fontsize=12)
    titre(ax, "Un bus dérouté reste « sur sa tournée » aux yeux de la règle",
          f"Rejeu sur la tournée réelle du groupe 1 — {LIVE['tournee']['points']} points, "
          f"{LIVE['tournee']['longueur_m'] / 1000:.1f} km")
    ax.set_ylim(-6, 104)
    finish(ax, grid_axis="y")
    pied(fig,
         "Une tournée de 50 arrêts repasse sans cesse dans le même quartier : le bus dévié se retrouve à côté d'un AUTRE\n"
         f"tronçon de sa propre polyligne. À 400 m de détour, il n'est en moyenne qu'à {median[detours.index(400)]:.0f} m de sa tournée — "
         "géométriquement\n« sur la route », opérationnellement non. C'est le piège du cycle fermé, déjà corrigé pour l'ETA et jamais transposé ici.")
    save(fig, "11_A1_couverture_spatiale_deviation")
    return fig


# ── A2 — le seuil de 250 m est trop haut ────────────────────────────────────
def fig_couverture_par_seuil():
    setup()
    lignes = LIVE["couverture_par_seuil"]
    seuils = [r["seuil_m"] for r in lignes]
    series = [("detour_200m_%", "Détour de 200 m"),
              ("detour_300m_%", "Détour de 300 m"),
              ("detour_400m_%", "Détour de 400 m")]

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    marqueurs = ["o", "s", "^"]  # encoder deux fois : couleur ET forme
    for (cle, label), coul, mk in zip(series, [PAL6[5], PAL6[3], PAL6[1]], marqueurs):
        ax.plot(seuils, [r[cle] for r in lignes], marker=mk, markersize=7,
                linewidth=2, color=coul, label=label)

    actuel, propose = SEUILS["deviation_m"], 120
    for x, txt, coul in [(actuel, f"actuel\n{actuel:.0f} m", "dimgrey"),
                         (propose, f"proposé\n{propose} m", ACCENT)]:
        ax.axvline(x, color=coul, linestyle="--", linewidth=1.3, zorder=0)
        note(ax, x + 6, 88, txt, fontsize=9, color=coul)

    ax.set_xlabel("Seuil de déviation configuré (m)", fontsize=12)
    ax.set_ylabel("Part du parcours couverte (%)", fontsize=12)
    titre(ax, "Abaisser le seuil double la couverture — sans fausse alarme mesurée",
          "Balayage du seuil à bruit GPS nul ; le coût en fausses alarmes est mesuré séparément")
    ax.set_ylim(-4, 100)
    legende(ax, loc="upper right", fontsize=10)
    finish(ax, grid_axis="y")
    pied(fig,
         "Aucune fausse alarme n'apparaît dès 100 m, même sous un bruit GPS de σ = 30 m — bien au-delà de l'erreur urbaine\n"
         "courante. Le seuil de 250 m achète donc une marge dont on n'a pas besoin, et la paie en couverture : passer à 120 m\n"
         "ferait passer la détection d'un détour de 300 m de 29 % à 55 % du parcours. C'est un réglage gratuit.")
    save(fig, "11_A2_couverture_par_seuil")
    return fig


# ── A3 — réglage des deux seuils temporels ──────────────────────────────────
def fig_balayages_temporels():
    setup()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=150)

    reb = LIVE["balayage_antirebond"]
    pings = [r["pings_consecutifs"] for r in reb]
    fa = [r["fausses_alarmes_h"] for r in reb]
    lat = [r["latence_s"] for r in reb]
    # rouge = le réglage fautif (une seule mesure suffit à alerter), vert = sûr
    couleurs = [ACCENT if p < SEUILS["deviation_pings"] else PAL6[4] for p in pings]
    ax1.bar(pings, fa, color=couleurs, width=0.6)
    for p, v in zip(pings, fa):
        ax1.text(p, v + 0.09, f"{v:.2f}", ha="center", color="dimgrey",
                 fontsize=10, weight="semibold")
    retenu = SEUILS["deviation_pings"]
    axl = ax1.twinx()
    axl.plot(pings, lat, marker="D", markersize=6, linewidth=1.8,
             color=PAL6[5], linestyle="--")
    # étiquetage direct : plus sûr qu'une boîte de légende qui flotte sur la courbe
    axl.annotate("latence de détection", (pings[-2], lat[-2]),
                 textcoords="offset points", xytext=(-14, 16), ha="right",
                 color=PAL6[5], fontsize=10, weight="medium")
    axl.set_ylabel("Latence (s)", fontsize=11, color="dimgrey")
    axl.tick_params(axis="y", length=0, labelcolor="dimgrey")
    axl.grid(False)
    ax1.set_xticks(pings)
    _marquer(ax1, pings, retenu)
    ax1.set_xlabel("Pings consécutifs exigés (anti-rebond)", fontsize=12)
    ax1.set_ylabel("Fausses alarmes par heure", fontsize=12)
    ax1.set_title(r"$\bf{(a)}$" + "  Anti-rebond de la déviation", loc="left",
                  fontsize=12, pad=9)
    ax1.set_ylim(0, max(fa) * 1.30)

    arr = LIVE["balayage_arret"]
    seuils = [r["seuil_min"] for r in arr]
    latences = [r["latence_s"] if r["latence_s"] is not None else np.nan for r in arr]
    detectee = [r["panne_detectee"] for r in arr]
    coul = [PAL6[4] if d else ACCENT for d in detectee]
    ax2.bar(seuils, [l if not np.isnan(l) else 0 for l in latences],
            color=coul, width=0.55)
    for s, l, d in zip(seuils, latences, detectee):
        if np.isnan(l):
            ax2.text(s, 12, "panne\nnon vue", ha="center", color=ACCENT,
                     fontsize=9, weight="semibold")
        else:
            ax2.text(s, l + 8, f"{l:.0f} s", ha="center", color="dimgrey",
                     fontsize=10, weight="semibold")
    actuel = SEUILS["arret_min"]
    ax2.set_xticks(seuils)
    _marquer(ax2, seuils, actuel)
    ax2.set_xlabel("Seuil d'arrêt prolongé (min)", fontsize=12)
    ax2.set_ylabel("Latence de détection de la panne (s)", fontsize=12)
    ax2.set_title(r"$\bf{(b)}$" + "  Seuil d'arrêt prolongé", loc="left",
                  fontsize=12, pad=9)
    ax2.set_ylim(0, np.nanmax(latences) * 1.22)

    fig.suptitle("Réglage mesuré des seuils temporels — rejeu sur la tournée réelle "
                 f"({LIVE['tournee']['points']} points, {LIVE['tournee']['longueur_m']/1000:.1f} km)",
                 fontsize=13, y=1.03, color="dimgrey")
    finish(ax1, ax2, grid_axis="y")
    fig.tight_layout()
    pied(fig,
         "Le réglage en production est signalé par son étiquette d'axe en gras.\n"
         "(a) Passer de 1 à 2 pings consécutifs supprime 3,34 fausses alarmes par heure pour 5 secondes de latence ; au-delà, on paie\n"
         "40 s de plus sans rien gagner — la valeur retenue est optimale, et c'est désormais une mesure et non une intuition.\n"
         "(b) Trois minutes suffisent à ne pas confondre un embouteillage avec une panne, et font gagner 2 minutes d'alerte : le choix\n"
         "de 5 minutes est conservateur — défendable, mais désormais chiffré.")
    save(fig, "11_A3_balayages_temporels")
    return fig


# ── A4 — les scénarios de rejeu ─────────────────────────────────────────────
def fig_scenarios():
    setup()
    evts = [(s["scenario"], e) for s in LIVE["scenarios"] for e in s["evenements"]]
    muets = [s for s in LIVE["scenarios"] if s["n_attendus"] == 0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 6), dpi=150,
                                   gridspec_kw={"width_ratios": [1.3, 1]})

    # (a) latence réelle vs plancher imposé par le seuil : ce que l'implémentation AJOUTE
    y = np.arange(len(evts))
    for i, (_, e) in enumerate(evts):
        plancher = e["plancher_theorique_s"]
        if e["detecte"]:
            lat = e["latence_s"]
            ax1.plot([plancher, lat], [i, i], color="lightgrey", linewidth=3,
                     solid_capstyle="round", zorder=1)
            ax1.scatter(plancher, i, s=110, color=NEUTRE, zorder=2)
            ax1.scatter(lat, i, s=140, color=PAL6[5], zorder=3)
            surcout = e["surcout_s"]
            ax1.text(max(lat, plancher) + 4, i, f"+{surcout:.0f} s",
                     va="center", fontsize=10.5, weight="semibold",
                     color=(ACCENT if surcout > 30 else "dimgrey"))
        else:
            ax1.scatter(plancher, i, s=110, color=NEUTRE, zorder=2)
            ax1.text(plancher + 4, i, "jamais détecté", va="center",
                     fontsize=10.5, weight="semibold", color=ACCENT)
    ax1.scatter([], [], s=110, color=NEUTRE, label="Plancher imposé par le seuil")
    ax1.scatter([], [], s=140, color=PAL6[5], label="Latence réellement mesurée")
    ax1.set_yticks(y, [e["libelle"] for _, e in evts])
    ax1.set_xlabel("Secondes après le début de l'événement", fontsize=12)
    ax1.set_title(r"$\bf{(a)}$" + "  Ce que l'implémentation ajoute au seuil",
                  loc="left", fontsize=12, pad=9)
    ax1.set_xlim(-18, 400)
    ax1.invert_yaxis()
    legende(ax1, loc="lower right", fontsize=10)

    # (b) scénarios où la règle DOIT rester muette
    y2 = np.arange(len(muets))
    fah = [s["fausses_alarmes_par_heure"] for s in muets]
    ax2.barh(y2, fah, color=[ACCENT if v > 0 else PAL6[4] for v in fah], height=0.55)
    for i, v in enumerate(fah):
        ax2.text(v + 0.04, i, f"{v:.2f}", va="center", color="dimgrey",
                 fontsize=10.5, weight="semibold")
    ax2.set_yticks(y2, [s["scenario"].replace("_", " ") for s in muets])
    ax2.set_xlabel("Fausses alarmes par heure", fontsize=12)
    ax2.set_title(r"$\bf{(b)}$" + "  Quand la règle doit rester muette",
                  loc="left", fontsize=12, pad=9)
    ax2.set_xlim(0, max(max(fah) * 1.45, 0.5))
    ax2.invert_yaxis()

    finish(ax1, ax2, grid_axis="x")
    fig.tight_layout()
    pied(fig,
         "(a) Séparer la latence du plancher distingue ce qu'on a CHOISI (un seuil de 5 min impose 5 min d'attente) de ce que\n"
         "l'implémentation AJOUTE. L'arrêt prolongé ne coûte qu'un ping de plus (+5 s) et la vitesse est instantanée — mais la déviation\n"
         "ajoute 75 s, et à 260 m pour un seuil de 250 m elle ne se déclenche jamais : c'est l'angle mort mesuré plus haut.\n"
         "(b) Cinq des six scénarios sans événement restent silencieux. Le sixième — un unique ping GPS aberrant — déclenche une alerte\n"
         "critique : VITESSE_EXCESSIVE n'a aucun anti-rebond, contrairement à la déviation. Les sauts GPS isolés existent ; les bus\n"
         "scolaires à 200 km/h, non.")
    save(fig, "11_A4_scenarios_rejeu")
    return fig


# ── B1 — LE résultat central : rappel par nature d'anomalie ─────────────────
def fig_rappel_par_nature():
    setup()
    det = ABL["validation_glissante"]["detecteurs"]
    ordre = ["seuil_surprise", "iforest_curated", "seuil_ratio", "iforest_all"]
    natures = ["franc", "contextuel", "surcharge"]
    x = np.arange(len(ordre))
    largeur = 0.26

    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=150)
    hachures = ["", "//", ".."]  # encoder deux fois : couleur ET texture
    for i, (nat, coul, hach) in enumerate(zip(natures, [PAL6[5], ACCENT, PAL6[2]], hachures)):
        vals = [det[d]["par_nature"][nat]["rappel"] * 100 for d in ordre]
        barres = ax.bar(x + (i - 1) * largeur, vals, largeur, color=coul,
                        hatch=hach, edgecolor="white", linewidth=0.6,
                        label=f"{nat.capitalize()} (n={det[ordre[0]]['par_nature'][nat]['n']})")
        for b, d in zip(barres, ordre):
            info = det[d]["par_nature"][nat]
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.6,
                    f"{info['detectes']}/{info['n']}", ha="center",
                    color="dimgrey", fontsize=9, weight="semibold")

    ax.set_xticks(x, [JOLI[d] for d in ordre])
    ax.set_ylabel("Rappel par nature d'anomalie (%)", fontsize=12)
    ax.set_ylim(0, 125)
    titre(ax, "Aucun détecteur ne domine : ils sont complémentaires",
          "Validation glissante à 4 blocs — 38 anomalies évaluées, et non 8")
    legende(ax, loc="upper center", fontsize=10, ncol=3)
    finish(ax, grid_axis="y")
    pied(fig,
         "« Surprise » attrape le CONTEXTUEL bien mieux (12/14) que l'Isolation Forest (3/14) — logique, puisque la variable a été conçue\n"
         "exactement pour cela : un ratio rapporté aux conditions. Le feature engineering fonctionne si bien que le modèle devient superflu.\n"
         "L'Isolation Forest n'apporte en propre que la SURCHARGE (7/7 contre 3/7) — logique aussi, c'est le seul à voir dwell et nb_montees.\n"
         "La documentation affirmait l'inverse : « un seuil univarié attrape surtout les francs ». La mesure dit le contraire.")
    save(fig, "11_B1_rappel_par_nature")
    return fig


# ── B2 — l'incertitude : 8 positifs ne départagent rien ─────────────────────
def fig_incertitude():
    setup()
    inc = ABL["incertitude"]
    gliss = ABL["validation_glissante"]["detecteurs"]
    ordre = ["iforest_curated", "seuil_surprise", "seuil_ratio", "iforest_all"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=150)

    y = np.arange(len(ordre))
    pts = [inc["detecteurs"][d]["PR_AUC_point"] for d in ordre]
    bas = [inc["detecteurs"][d]["IC95_bas"] for d in ordre]
    haut = [inc["detecteurs"][d]["IC95_haut"] for d in ordre]
    err = [np.array(pts) - np.array(bas), np.array(haut) - np.array(pts)]
    ax1.errorbar(pts, y, xerr=err, fmt="o", markersize=10, capsize=6,
                 color=PAL6[5], ecolor=NEUTRE, elinewidth=2.2, capthick=2.2)
    for i, (p, b, h) in enumerate(zip(pts, bas, haut)):
        ax1.text(p, i + 0.22, f"{p:.3f}", ha="center", color="dimgrey",
                 fontsize=10, weight="semibold")
        ax1.text(h + 0.015, i, f"[{b:.2f} ; {h:.2f}]", va="center",
                 color="dimgrey", fontsize=9)
    ax1.set_yticks(y, [JOLI[d] for d in ordre])
    ax1.set_xlabel("PR-AUC (bloc de test unique)", fontsize=12)
    ax1.set_xlim(0, 1.30)
    ax1.invert_yaxis()
    ax1.set_title(r"$\bf{(a)}$" + f"  Bootstrap {inc['n_boot']} tirages sur "
                  f"{inc['n_positifs']} positifs", loc="left", fontsize=12, pad=9)

    moy = [gliss[d]["PR_AUC_moyen"] for d in ordre]
    sd = [gliss[d]["PR_AUC_ecart_type"] for d in ordre]
    couleurs = [ACCENT if d == "seuil_surprise" else NEUTRE for d in ordre]
    ax2.barh(y, moy, xerr=sd, height=0.55, color=couleurs,
             error_kw=dict(ecolor="dimgrey", elinewidth=1.6, capsize=5))
    for i, (m, s) in enumerate(zip(moy, sd)):
        ax2.text(m + s + 0.02, i, f"{m:.3f} ± {s:.3f}", va="center",
                 color="dimgrey", fontsize=10, weight="semibold")
    ax2.set_yticks(y, [JOLI[d] for d in ordre])
    ax2.set_xlabel("PR-AUC moyen (validation glissante, 38 positifs)", fontsize=12)
    ax2.set_xlim(0, 1.22)
    ax2.invert_yaxis()
    ax2.set_title(r"$\bf{(b)}$" + "  Le classement s'inverse", loc="left",
                  fontsize=12, pad=9)

    finish(ax1, ax2, grid_axis="x")
    fig.tight_layout()
    pied(fig,
         "(a) Sur le bloc de test unique du benchmark gelé, les intervalles des deux premiers détecteurs se recouvrent largement : publier\n"
         "une PR-AUC de 0,9127 à quatre décimales sur 8 positifs donne une précision que la donnée ne porte pas.\n"
         "(b) En enchaînant 4 blocs successifs — 38 anomalies au lieu de 8 — le classement s'inverse : un seuil univarié bat le modèle\n"
         "multivarié. La première question à poser devant un classement, c'est combien d'observations le départagent.")
    save(fig, "11_B2_incertitude_classement")
    return fig


# ── B3 — PR-AUC par bloc ────────────────────────────────────────────────────
def fig_folds():
    setup()
    gliss = ABL["validation_glissante"]["detecteurs"]
    ordre = ["seuil_surprise", "iforest_curated", "seuil_ratio", "iforest_all"]
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    marqueurs = ["o", "s", "^", "D"]
    for d, coul, mk in zip(ordre, [ACCENT, PAL6[5], PAL6[3], NEUTRE], marqueurs):
        vals = gliss[d]["PR_AUC_par_fold"]
        ax.plot(range(1, len(vals) + 1), vals, marker=mk, markersize=8,
                linewidth=2, color=coul, label=JOLI[d])
    ax.set_xticks(range(1, len(gliss[ordre[0]]["PR_AUC_par_fold"]) + 1))
    ax.set_xlabel("Bloc de test (origine glissante, entraînement sur le passé seul)",
                  fontsize=12)
    ax.set_ylabel("PR-AUC", fontsize=12)
    ax.set_ylim(0.33, 1.10)
    titre(ax, "Stabilité bloc par bloc — un seul bloc aurait désigné un autre gagnant",
          "Origine glissante : chaque bloc est évalué par un modèle entraîné uniquement sur son passé")
    legende(ax, loc="lower right", fontsize=10)
    finish(ax, grid_axis="y", cadre=True)
    pied(fig,
         "Le bloc 1 est celui du benchmark gelé, et c'est le seul où l'Isolation Forest devance « surprise ». Les trois blocs suivants\n"
         "l'inversent. Un classement établi sur un unique découpage temporel mesure autant le découpage que les détecteurs.")
    save(fig, "11_B3_pr_auc_par_bloc")
    return fig


# ── B4 — la fuite soupçonnée n'existe pas ───────────────────────────────────
def fig_fuite():
    setup()
    f = ABL["fuite"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=150,
                                   gridspec_kw={"width_ratios": [1.25, 1]})

    cats, gen, est = [], [], []
    for famille in ("trafic", "meteo"):
        for k in f["coefficients_generateur"][famille]:
            if k in ("fluide", "ensoleille"):
                continue  # référence à 1.0, sans information
            cats.append(f"{famille[:3]}. {k}")
            gen.append(f["coefficients_generateur"][famille][k])
            est.append(f["coefficients_estimes"][famille][k])
    x = np.arange(len(cats))
    ax1.bar(x - 0.2, gen, 0.4, color=NEUTRE, label="Codé en dur (générateur)")
    ax1.bar(x + 0.2, est, 0.4, color=PAL6[5], hatch="//", edgecolor="white",
            linewidth=0.6, label="Ré-estimé depuis les seules données")
    for xi, (g, e) in enumerate(zip(gen, est)):
        ax1.text(xi - 0.2, g + 0.015, f"{g:.2f}", ha="center", color="dimgrey", fontsize=9)
        ax1.text(xi + 0.2, e + 0.015, f"{e:.2f}", ha="center", color="dimgrey", fontsize=9)
    ax1.set_xticks(x, cats, rotation=18, ha="right")
    ax1.set_ylabel("Coefficient multiplicatif", fontsize=12)
    ax1.set_ylim(0.9, max(gen) * 1.12)
    ax1.set_title(r"$\bf{(a)}$" + "  Les coefficients se retrouvent depuis un historique ordinaire",
                  loc="left", fontsize=12, pad=9)
    legende(ax1, loc="upper left", fontsize=10)

    ordre = ["seuil_surprise", "iforest_curated", "seuil_ratio"]
    dur = ABL["validation_glissante"]["detecteurs"]
    estim = ABL["validation_glissante_coeffs_estimes"]["detecteurs"]
    y = np.arange(len(ordre))
    a = [dur[d]["PR_AUC_moyen"] for d in ordre]
    b = [estim[d]["PR_AUC_moyen"] for d in ordre]
    # même encodage qu'en (a) : la légende du panneau (a) vaut pour les deux
    ax2.barh(y - 0.19, a, 0.38, color=NEUTRE)
    ax2.barh(y + 0.19, b, 0.38, color=PAL6[5], hatch="//", edgecolor="white",
             linewidth=0.6)
    for i, (va, vb) in enumerate(zip(a, b)):
        delta = vb - va
        ax2.text(max(va, vb) + 0.015, i,
                 f"{delta:+.3f}", va="center", fontsize=10, weight="semibold",
                 color=(PAL6[5] if delta >= 0 else ACCENT))
    ax2.set_yticks(y, [JOLI[d] for d in ordre])
    ax2.set_xlabel("PR-AUC moyen (validation glissante)", fontsize=12)
    ax2.set_xlim(0, 1.12)
    ax2.invert_yaxis()
    ax2.set_title(r"$\bf{(b)}$" + "  Le gagnant ne doit rien à la fuite", loc="left",
                  fontsize=12, pad=9)

    finish(ax1, grid_axis="y")
    finish(ax2, grid_axis="x")
    fig.tight_layout()
    pied(fig,
         "La variable « surprise » reprenait exactement les coefficients du générateur : un soupçon sérieux de circularité, d'autant plus\n"
         "gênant qu'elle est le détecteur gagnant. On les a donc ré-estimés depuis les seules données d'entraînement de chaque bloc\n"
         "(médiane stratifiée du log-ratio), sans jamais regarder le générateur. « Surprise » fait alors marginalement MIEUX (+0,003).\n"
         "La structure multiplicative du trafic est récupérable depuis un historique ordinaire — ce qu'un exploitant possède déjà.")
    save(fig, "11_B4_fuite_generateur")
    return fig


# ── B5 — le budget d'alerte, pour l'exploitant ──────────────────────────────
def fig_budget():
    setup()
    b = ABL["budget"]
    budgets = [r["budget_%"] for r in b]
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    for det, coul, mk in [("seuil_surprise", ACCENT, "o"),
                          ("iforest_curated", PAL6[5], "s")]:
        ax.plot(budgets, [r[f"{det}_R"] * 100 for r in b], marker=mk, markersize=8,
                linewidth=2.2, color=coul, label=f"{JOLI[det]} — rappel")
        ax.plot(budgets, [r[f"{det}_P"] * 100 for r in b], marker=mk, markersize=6,
                linewidth=1.8, linestyle="--", alpha=0.75, color=coul,
                label=f"{JOLI[det]} — précision")
    actuel = 1.28
    ax.axvline(actuel, color="dimgrey", linestyle=":", linewidth=1.4, zorder=0)
    note(ax, actuel + 0.12, 12, f"budget gelé\n{actuel} %", fontsize=9)
    ax.set_xlabel("Budget d'alerte (% des trajets signalés)", fontsize=12)
    ax.set_ylabel("Précision / rappel (%)", fontsize=12)
    titre(ax, "Arbitrer avec l'exploitant, plutôt que lui imposer un seuil",
          "Trait plein = rappel · trait pointillé = précision")
    legende(ax, loc="center right", fontsize=9)
    finish(ax, grid_axis="y", cadre=True)
    pied(fig,
         "La question de l'administration n'est pas « quelle PR-AUC ? » mais « combien d'alertes par jour puis-je traiter ? ». Élargir le\n"
         "budget fait monter le rappel et chuter la précision — à 2 %, l'Isolation Forest atteint 100 % de rappel sur ce bloc. La courbe\n"
         "permet de discuter le réglage avec l'exploitant au lieu de le lui imposer.")
    save(fig, "11_B5_budget_alerte")
    return fig


# ── B6 — l'union à budget égalisé ───────────────────────────────────────────
def fig_combinaison():
    setup()
    c = ABL["combinaison"]
    ordre = ["seuil_surprise", "iforest_curated", "union_budget_egal"]
    noms = ["Seuil surprise", "IForest curées", "Union (budget égalisé)"]
    natures = ["franc", "contextuel", "surcharge"]
    x = np.arange(len(ordre))
    fig, ax = plt.subplots(figsize=(11, 6.2), dpi=150)
    bas = np.zeros(len(ordre))
    for nat, coul, hach in zip(natures, [PAL6[5], ACCENT, PAL6[2]], ["", "//", ".."]):
        vals = np.array([c[d]["par_nature"][nat]["detectes"] for d in ordre])
        ax.bar(x, vals, 0.55, bottom=bas, color=coul, hatch=hach,
               edgecolor="white", linewidth=0.7,
               label=f"{nat.capitalize()} (n={c[ordre[0]]['par_nature'][nat]['n']})")
        for xi, (v, bb) in enumerate(zip(vals, bas)):
            if v > 0:
                ax.text(xi, bb + v / 2, str(v), ha="center", va="center",
                        color="white", fontsize=11, weight="bold")
        bas += vals
    for xi, d in enumerate(ordre):
        ax.text(xi, bas[xi] + 0.7,
                f"{c[d]['alertes_emises']} alertes · P={c[d]['precision']:.2f} · R={c[d]['rappel']:.2f}",
                ha="center", color="dimgrey", fontsize=10, weight="semibold")
    ax.set_xticks(x, noms)
    ax.set_ylabel("Anomalies détectées (sur 38)", fontsize=12)
    ax.set_ylim(0, bas.max() * 1.30)
    titre(ax, "À budget d'alerte égal, l'union est un compromis — pas un gagnant",
          "Union calibrée par dichotomie pour émettre le MÊME nombre d'alertes qu'un détecteur seul")
    legende(ax, loc="upper right", fontsize=10)
    finish(ax, grid_axis="y")
    pied(fig,
         "Unir les deux détecteurs semble évident, mais une union qui alerte deux fois plus n'a aucun mérite : la règle du budget égalisé\n"
         "s'applique. Une fois calibrée à nombre d'alertes constant, l'union récupère la surcharge (6/7) en perdant du contextuel (7/14\n"
         "contre 12/14). Elle se place entre les deux détecteurs sans en dépasser aucun : à budget égal, « surprise » seul reste devant.")
    save(fig, "11_B6_union_budget_egal")
    return fig


#: Toutes les figures, dans l'ordre du mémoire. Chaque fonction rend son
#: ``Figure`` : appelée depuis un notebook, elle s'affiche en ligne ; appelée
#: depuis ce script, elle est refermée après enregistrement.
FIGURES_MEMOIRE = [
    fig_couverture_spatiale, fig_couverture_par_seuil, fig_balayages_temporels,
    fig_scenarios, fig_rappel_par_nature, fig_incertitude, fig_folds,
    fig_fuite, fig_budget, fig_combinaison,
]

if __name__ == "__main__":
    for f in FIGURES_MEMOIRE:
        plt.close(f())
    print(f"\n{len(FIGURES_MEMOIRE)} figures MS11 générées.")
