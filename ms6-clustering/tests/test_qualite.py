"""
Tests du garde-fou qualité — et du cliquet qui l'avait bloqué cinq semaines.

Le défaut, rejoué ici en `test_le_cliquet_du_17_07_ne_peut_plus_se_reproduire` : la référence est
réécrite **uniquement si le verdict est OK** (`maybe_maj_baseline`). Une référence trop haute rend
donc tout run `DEGRADE`… ce qui l'empêche d'être mise à jour. Elle reste trop haute pour toujours.
Du 17/07 au 24/08, le service a affiché DEGRADE en continu avec une référence à 0,5183 pour un
niveau réellement atteignable de 0,4334.

Deux protections sont testées ici :
- **le plafond** — la référence ne peut jamais dépasser l'ancre (le point de conception) ;
- **le contexte** — une référence prise avec d'autres bus ou un autre rayon est ignorée.
"""
from __future__ import annotations

import pytest

import quality
from quality import evaluer_qualite, reference_applicable


CTX = {"n_eleves": 300, "capacity": 50, "rayon_max_m": 0.0,
       "n_disperses": 17, "n_non_affectes": 0}


def metriques(silhouette: float, faisable: bool = True) -> dict:
    return {"silhouette": silhouette, "faisable": faisable, "taille_max": 50,
            "compacite_med_m": 734.2, "compacite_max_m": 2804.1}


def reference(silhouette: float, **kw) -> dict:
    base = {"silhouette": silhouette, "compacite_max_m": 2804.1, "compacite_med_m": 734.2,
            "taille_max": 50, "faisable": True, "n_disperses_total": 17,
            "n_eleves": 300, "capacity": 50, "rayon_max_m": 0.0}
    base.update(kw)
    return base


# ── Le cliquet ───────────────────────────────────────────────────────────────
def test_le_cliquet_du_17_07_ne_peut_plus_se_reproduire():
    """La référence réellement trouvée en production (0,5183) face au run du jour (0,4256).

    Avant le plafond : chute de 17,9 % → DEGRADE → référence jamais réécrite → blocage définitif.
    Après : la référence est ramenée à l'ancre, l'écart devient négligeable, le verdict repasse OK
    et le mécanisme roulant peut repartir.
    """
    v = evaluer_qualite(metriques(0.4256), CTX, baseline=reference(0.5183))
    assert v["niveau"] == "OK", v["raisons"]


def test_une_reference_plus_basse_que_l_ancre_est_respectee():
    """Le plafond ne doit pas effacer la détection de dérive : une référence basse reste utilisée."""
    v = evaluer_qualite(metriques(0.20), CTX, baseline=reference(0.40))
    assert v["niveau"] in ("DEGRADE", "CRITIQUE")
    assert any("silhouette" in r for r in v["raisons"])


def test_la_derive_lente_reste_detectee():
    """Ce que le plafond ne doit surtout pas casser : une vraie régression déclenche toujours.

    0,35 est choisi au-dessus du plancher absolu (0,75 × 0,4256 = 0,319) pour isoler la
    comparaison RELATIVE : en dessous, c'est CRITIQUE qui l'emporte et on ne testerait plus rien.
    """
    v = evaluer_qualite(metriques(0.35), CTX, baseline=reference(0.4256))
    assert v["niveau"] == "DEGRADE", v["raisons"]


# ── Le contexte ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("modif,applicable", [
    ({}, True),
    ({"capacity": 60}, False),
    ({"rayon_max_m": 1500.0}, False),
    ({"n_eleves": 340}, True),          # l'effectif bouge naturellement : n'invalide pas
], ids=["identique", "capacite_changee", "rayon_change", "effectif_different"])
def test_reference_applicable(modif, applicable):
    ref = reference(0.4256, **modif)
    assert (reference_applicable(ref, CTX) is not None) is applicable


def test_une_reference_d_un_autre_contexte_n_impose_rien():
    """Comparer une qualité obtenue avec des bus de 60 places à une autre obtenue avec 50 n'a
    pas de sens — mieux vaut ne pas comparer que comparer à tort."""
    v = evaluer_qualite(metriques(0.35), CTX, baseline=reference(0.4256, capacity=60))
    assert v["niveau"] == "OK", v["raisons"]     # plus de comparaison relative possible
    # ...et l'exploitant doit savoir POURQUOI : « écartée » et non « aucune référence », qui
    # laisserait croire à une première évaluation.
    assert any("écartée" in r for r in v["raisons"]), v["raisons"]


def test_une_reference_ancienne_sans_contexte_reste_utilisable():
    """Rétrocompatibilité : les fichiers écrits avant l'enregistrement du contexte."""
    ancienne = {"silhouette": 0.4256, "compacite_max_m": 2804.1, "n_disperses_total": 17}
    assert reference_applicable(ancienne, CTX) is not None


# ── Les garde-fous qui ne changent pas ───────────────────────────────────────
def test_capacite_depassee_reste_critique():
    v = evaluer_qualite(metriques(0.50, faisable=False), CTX, baseline=reference(0.4256))
    assert v["niveau"] == "CRITIQUE"


def test_plancher_absolu_toujours_actif():
    """Sous 0,75 × l'ancre, c'est CRITIQUE quelle que soit la référence — le filet anti-effondrement."""
    v = evaluer_qualite(metriques(0.10), CTX, baseline=reference(0.4256))
    assert v["niveau"] == "CRITIQUE"


def test_l_ancre_est_la_partition_complete():
    """L'ancre doit être la silhouette de la partition **finale**, pas celle du cœur.

    Les deux valeurs vivent dans `production_config.json` ; comparer la mesure d'un run (300
    élèves) à la valeur du cœur (283) reviendrait à comparer deux grandeurs différentes.
    """
    assert quality._silhouette_gelee() == pytest.approx(0.4256, abs=1e-6)
