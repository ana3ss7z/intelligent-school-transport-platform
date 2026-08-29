"""Style commun des figures ajoutées au mémoire PFE.

Ce module est un **utilitaire de tracé**, pas du code de production : il ne lit
que des artefacts déjà gelés et n'écrit que des PNG/PDF dans ``notebooks/figures/``.

Conventions reprises de la skill ``matplotlib`` du projet (``style-reference.md``) :
police DejaVu Sans, thème ``whitegrid``, despine intégral, encres d'annotation en
``dimgrey``, cadre de légende blanc discret, export PDF + PNG en 300 dpi (le
mémoire est un rendu de publication).

Usage type dans une cellule de notebook ::

    from viz_memoire import setup, finish, save, ACCENT, NEUTRE
    setup()
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    ...
    finish(ax)
    save(fig, "11_couverture_deviation")
"""

from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

# ── Identité visuelle (tokens immuables de la skill) ────────────────────────
ACCENT = "#bd0c0c"          # emphase sélective : le résultat qui compte
NEUTRE = "#9e9e9e"          # éléments de comparaison, non primaires
TRAFFIC = ["#33a02c", "#fdbf6f", "#e31a1c"]      # vert / ambre / rouge
DIVERGENT = ["#d73027", "#fc8d59", "#fee090", "#4575b4"]

#: Palette séquentielle par défaut (cubehelix, sûre pour daltoniens).
PAL6 = sns.cubehelix_palette(6, rot=-0.25, light=0.7)

#: Dossier de sortie, résolu par rapport à CE fichier (robuste au cwd du kernel).
FIGURES = Path(__file__).resolve().parent / "figures"

DPI_RENDU = 300  # mémoire = rendu de publication


def setup():
    """Applique le thème seaborn commun. À appeler en tête de chaque cellule."""
    sns.set_theme(font_scale=1.0, style="whitegrid", font="DejaVu Sans")


def finish(*axes, grid_axis=None, cadre=False):
    """Nettoyage final : despine, ticks adoucis, grille sélective.

    Parameters
    ----------
    *axes : matplotlib.axes.Axes
        Un ou plusieurs axes à nettoyer.
    grid_axis : {"x", "y", None}
        Axe sur lequel conserver une grille légère. ``None`` = aucune grille.
    cadre : bool
        Encadre le fond de l'axe (recommandé en multi-panneaux et pour les
        nuages/courbes qui flottent dans l'espace).
    """
    sns.despine(left=True, bottom=True)
    for ax in axes:
        ax.tick_params(axis="both", which="both", length=0, labelcolor="dimgrey")
        if grid_axis in ("x", "y"):
            ax.grid(False)
            ax.grid(alpha=0.7, linewidth=1, axis=grid_axis)
        else:
            ax.grid(False)
        if cadre:
            ax.patch.set_edgecolor("lightgrey")
            ax.patch.set_linewidth(0.8)


def legende(ax, **kw):
    """Légende au cadre blanc discret, texte en ``dimgrey``."""
    params = dict(frameon=True, facecolor="white", framealpha=0.8,
                  edgecolor="lightgrey", labelcolor="dimgrey")
    params.update(kw)
    return ax.legend(**params)


def note(ax, x, y, texte, **kw):
    """Annotation ponctuelle DANS l'aire de tracé (repère, seuil, flèche).

    À réserver aux étiquettes courtes qu'on peut placer sûrement. Pour une
    explication de plusieurs lignes, utiliser :func:`pied` — une annotation
    longue posée dans l'aire de données finit toujours par heurter une barre.
    """
    params = dict(color="dimgrey", fontsize=10, weight="medium")
    params.update(kw)
    return ax.text(x, y, texte, **params)


def titre(ax, principal, sous=None, fontsize=13):
    """Titre à gauche, avec une ligne de contexte optionnelle en dessous."""
    ax.set_title(principal, loc="left", fontsize=fontsize,
                 pad=26 if sous else 10)
    if sous:
        ax.text(0, 1.035, sous, transform=ax.transAxes, ha="left", va="bottom",
                color="dimgrey", fontsize=fontsize - 2.5)


def pied(fig, texte, y=-0.01, fontsize=10):
    """Explication placée SOUS la figure — jamais en collision avec les données.

    C'est la place d'une lecture en plusieurs lignes : le rectangle de tracé
    reste réservé aux données, et ``bbox_inches="tight"`` embarque le texte.
    """
    return fig.text(0.0, y, texte, ha="left", va="top", color="dimgrey",
                    fontsize=fontsize)


def save(fig, nom):
    """Enregistre la figure en PDF + PNG dans ``notebooks/figures/``.

    C'est la **seule** écriture autorisée par le protocole : aucun artefact
    gelé (``*.pkl``, ``*_config.json``) n'est touché.
    """
    FIGURES.mkdir(exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIGURES / f"{nom}.{ext}", dpi=DPI_RENDU, bbox_inches="tight")
    print(f"figure enregistrée : figures/{nom}.png  (+ .pdf, {DPI_RENDU} dpi)")
