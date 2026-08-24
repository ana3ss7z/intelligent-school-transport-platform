"""
Filet de sécurité autour du choix du nombre de bus (`selection.choisir_k`).

Pourquoi ces tests existent
---------------------------
MS6 n'avait **aucun test**. Or on s'apprête à modifier la règle qui décide combien de bus l'école
doit affréter — c'est la décision la plus lourde de conséquences du service. Ces tests sont écrits
**avant** la modification, pour deux raisons :

1. **Prouver que le correctif ne casse rien.** Les invariants ci-dessous (capacité respectée, tous
   les élèves affectés, dispersés stables) doivent tenir avant *et* après. S'ils tombent, on
   s'arrête.
2. **Décrire le défaut à corriger.** `test_le_nombre_de_bus_ne_depend_pas_de_l_ordre` est marqué
   `xfail` : il **échoue aujourd'hui**, et c'est voulu. Il passera une fois `choisir_k` corrigé —
   c'est lui qui définit ce qu'on cherche à obtenir, pas un commentaire dans un fichier.

    pytest ms6-clustering/tests -q
"""
from __future__ import annotations

import collections
import functools

import pytest

from config import settings
from clustering import _compute_production
from donnees import CAPACITE, ordres, permuter


@functools.lru_cache(maxsize=16)
def _resultat(nom_ordre: str):
    """Exécute le pipeline de production pour un ordre donné (mis en cache : ~0,3 s par appel)."""
    perm = dict(ordres())[nom_ordre]
    ids, XY, D = permuter(perm)
    res = _compute_production(ids, XY, D, CAPACITE, settings.k_margin,
                              settings.min_silhouette, settings.kmedoids_iters)
    return ids, res


TOUS_LES_ORDRES = [nom for nom, _ in ordres()]


# ── Invariants : vrais avant le correctif, et ils doivent le rester après ─────
@pytest.mark.parametrize("nom_ordre", TOUS_LES_ORDRES)
def test_aucun_groupe_ne_depasse_la_capacite(nom_ordre):
    """La contrainte dure du métier : un bus de 50 places ne transporte pas 51 enfants."""
    _, res = _resultat(nom_ordre)
    tailles = collections.Counter(g for g in res["mapping"].values() if g != 999)
    assert tailles, "aucun groupe produit"
    assert max(tailles.values()) <= CAPACITE, f"groupe surchargé : {max(tailles.values())} élèves"


@pytest.mark.parametrize("nom_ordre", TOUS_LES_ORDRES)
def test_tous_les_eleves_recoivent_un_groupe(nom_ordre):
    """Aucun élève ne doit disparaître du plan de transport — même les dispersés ont le groupe 999."""
    ids, res = _resultat(nom_ordre)
    assert set(res["mapping"]) == {int(i) for i in ids}
    assert all(g == 999 or 1 <= g <= res["k"] for g in res["mapping"].values())


@pytest.mark.parametrize("nom_ordre", TOUS_LES_ORDRES)
def test_les_disperses_ne_dependent_pas_de_l_ordre(nom_ordre):
    """Les élèves isolés sont détectés par DBSCAN sur la matrice routière.

    Contrairement au choix du nombre de bus, cette détection **est** stable : l'ensemble des points
    de bruit d'un DBSCAN ne dépend pas de l'ordre des lignes. C'est utile comme point de repère —
    si ce test se met à échouer, c'est que quelque chose de bien plus profond a bougé.
    """
    _, res = _resultat(nom_ordre)
    assert res["n_disperses"] == 17


# ── La propriété que le correctif devait établir ─────────────────────────────
def test_le_nombre_de_bus_ne_depend_pas_de_l_ordre():
    """Mêmes élèves, mêmes adresses, même graine : le nombre de bus doit être le même.

    Ce test a d'abord été écrit **en `xfail`** : il échouait, et c'est ce qui définissait l'objectif.
    Avant le correctif, sur 30 permutations, le service répondait k=7 (57 %), k=8 (7 %), k=9 (37 %) —
    deux bus et deux chauffeurs d'écart selon l'ordre dans lequel la base rendait ses lignes.
    """
    ks = {nom: _resultat(nom)[1]["k"] for nom in TOUS_LES_ORDRES}
    assert len(set(ks.values())) == 1, f"le nombre de bus varie selon l'ordre : {ks}"


def test_non_regression_sept_bus():
    """La valeur retenue reste celle que le service produit aujourd'hui : **7 bus**.

    Le correctif devait stabiliser la réponse, pas la déplacer. Si ce test tombe, c'est que le
    comportement métier a changé — il faut s'arrêter et comprendre avant d'aller plus loin.
    """
    _, res = _resultat("trie_par_id")
    assert res["k"] == 7
