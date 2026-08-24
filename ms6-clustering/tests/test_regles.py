"""
Tests unitaires de la règle de choix (`selection.choisir_k`) et de la mémoire (`etat`).

Complément volontairement **rapide** aux tests de `test_selection.py`, qui font tourner le vrai
pipeline sur 300 élèves (~20 s). Ici on fabrique des lignes Pareto à la main : chaque test isole
une règle et s'exécute en quelques millisecondes. C'est ce qui permet de couvrir les cas limites —
mémoire absente, mémoire corrompue, flotte rétrécie — qu'on ne peut pas provoquer facilement en
bout de chaîne.
"""
from __future__ import annotations

import json
import os

import pytest

import etat
from selection import EPSILON_MAX, EPSILON_MIN, choisir_k, epsilon_entre


def ligne(k: int, note: float, dispersion: float = 0.0, faisable: bool = True) -> dict:
    """Une ligne Pareto minimale — juste ce que `choisir_k` regarde."""
    return {"k": k, "silhouette_mediane": note, "silhouette_dispersion": dispersion,
            "faisable": faisable, "labels": None, "medoids": []}


# ── Le filtre de faisabilité, conservé du code d'origine ─────────────────────
def test_une_solution_infaisable_n_est_jamais_retenue():
    """Même bien meilleure : un groupe qui dépasse la capacité d'un bus est inutilisable."""
    rows = [ligne(2, 0.90, faisable=False), ligne(3, 0.40)]
    assert choisir_k(rows)["k"] == 3


def test_si_rien_n_est_faisable_on_ne_renvoie_pas_rien():
    """Repli du code d'origine : mieux vaut une solution imparfaite que pas de plan de transport."""
    rows = [ligne(2, 0.30, faisable=False), ligne(3, 0.50, faisable=False)]
    assert choisir_k(rows)["k"] in (2, 3)


def test_aucune_ligne_leve_une_erreur_explicite():
    with pytest.raises(ValueError):
        choisir_k([])


# ── La parcimonie et la marge ε ──────────────────────────────────────────────
def test_a_qualite_indiscernable_on_prend_le_plus_petit_k():
    """Un bus de moins, c'est un chauffeur de moins — et l'écart n'est pas mesurable."""
    rows = [ligne(6, 0.430, 0.02), ligne(7, 0.433, 0.02)]
    assert choisir_k(rows)["k"] == 6


def test_un_ecart_net_n_est_pas_efface_par_la_marge():
    """La parcimonie ne doit pas devenir « toujours le moins de bus »."""
    rows = [ligne(6, 0.300, 0.001), ligne(7, 0.433, 0.001)]
    assert choisir_k(rows)["k"] == 7


def test_epsilon_ne_depend_que_des_deux_candidats_compares():
    """Le bruit d'un troisième `k` ne doit pas élargir la marge des autres.

    C'est l'erreur qu'une première version du correctif contenait : ε était calculé comme la plus
    grande dispersion de TOUS les candidats. Un `k=9` très instable faisait alors passer `k=6`
    pour l'égal de `k=7`, et le service répondait 6 bus.
    """
    stable_a, stable_b = ligne(6, 0.392, 0.0004), ligne(7, 0.433, 0.0004)
    tres_bruite = ligne(9, 0.400, 0.0486)
    assert epsilon_entre(stable_a, stable_b) < 0.041      # l'écart réel entre k=6 et k=7
    assert choisir_k([stable_a, stable_b, tres_bruite])["k"] == 7


def test_epsilon_reste_dans_ses_bornes():
    assert epsilon_entre(ligne(1, 0.5, 0.0), ligne(2, 0.5, 0.0)) == EPSILON_MIN
    assert epsilon_entre(ligne(1, 0.5, 9.9), ligne(2, 0.5, 0.0)) == EPSILON_MAX


def test_epsilon_zero_reproduit_l_ancien_comportement():
    """`epsilon=0.0` = argmax strict, conservé pour comparer avant/après."""
    rows = [ligne(6, 0.4329, 0.02), ligne(7, 0.4330, 0.02)]
    assert choisir_k(rows, epsilon=0.0)["k"] == 7
    assert choisir_k(rows)["k"] == 6


# ── L'hystérésis ─────────────────────────────────────────────────────────────
def test_la_flotte_en_place_est_conservee_si_elle_tient():
    """Le cœur de l'hystérésis : ne pas redistribuer l'école pour un écart non mesurable."""
    rows = [ligne(6, 0.430, 0.02), ligne(7, 0.433, 0.02)]
    assert choisir_k(rows)["k"] == 6                       # sans mémoire : parcimonie
    assert choisir_k(rows, k_precedent=7)["k"] == 7        # avec mémoire : on garde


def test_la_flotte_en_place_cede_si_elle_est_nettement_battue():
    rows = [ligne(6, 0.200, 0.001), ligne(7, 0.433, 0.001)]
    assert choisir_k(rows, k_precedent=6)["k"] == 7


def test_une_flotte_devenue_infaisable_est_oubliee():
    """`pareto` n'émet que les `k` capables d'accueillir tout le monde : si l'ancien `k` n'y
    figure plus, c'est qu'il ne tient plus. Aucun test supplémentaire n'est nécessaire."""
    rows = [ligne(7, 0.433, 0.001), ligne(8, 0.430, 0.001)]
    assert choisir_k(rows, k_precedent=6)["k"] == 7


# ── La mémoire sur disque ────────────────────────────────────────────────────
def test_ecriture_relecture(tmp_path):
    f = str(tmp_path / "sel.json")
    etat.enregistrer(7, 300, 50, 0.0, chemin=f)
    lu = etat.charger(f)
    assert lu["k"] == 7 and lu["n"] == 300 and lu["capacity"] == 50


def test_memoire_absente_ne_leve_pas(tmp_path):
    assert etat.charger(str(tmp_path / "inexistant.json")) is None


def test_memoire_corrompue_est_ignoree(tmp_path):
    """Un service qui refuse de démarrer à cause d'un fichier de confort serait pire que le
    problème qu'on corrige."""
    f = tmp_path / "sel.json"
    f.write_text("{ceci n'est pas du JSON", encoding="utf-8")
    assert etat.charger(str(f)) is None


def test_memoire_sans_k_est_ignoree(tmp_path):
    f = tmp_path / "sel.json"
    f.write_text(json.dumps({"n": 300}), encoding="utf-8")
    assert etat.charger(str(f)) is None


@pytest.mark.parametrize("etat_memorise,capacity,rayon,flotte,attendu", [
    ({"k": 7, "capacity": 50, "rayon_max_m": 0.0}, 50, 0.0, None, 7),
    ({"k": 7, "capacity": 50, "rayon_max_m": 0.0}, 50, 0.0, 10, 7),
    ({"k": 7, "capacity": 50, "rayon_max_m": 0.0}, 60, 0.0, None, None),   # capacité changée
    ({"k": 7, "capacity": 50, "rayon_max_m": 0.0}, 50, 1500.0, None, None),  # rayon changé
    ({"k": 7, "capacity": 50, "rayon_max_m": 0.0}, 50, 0.0, 6, None),      # flotte rétrécie
    (None, 50, 0.0, None, None),                                          # aucune mémoire
], ids=["contexte_identique", "flotte_suffisante", "capacite_changee",
        "rayon_change", "flotte_retrecie", "sans_memoire"])
def test_contexte_compatible(etat_memorise, capacity, rayon, flotte, attendu):
    """Un `k` mémorisé n'a de sens que pour un contexte donné.

    « 7 bus » ne veut plus rien dire si la capacité passe à 60 places, si la contrainte de rayon
    change, ou s'il ne reste que 6 bus dans la flotte.
    """
    assert etat.contexte_compatible(etat_memorise, capacity, rayon, flotte) == attendu


def test_ecriture_atomique_ne_laisse_pas_de_fichier_tronque(tmp_path, monkeypatch):
    """Si l'écriture échoue, l'ancien contenu doit rester intact — jamais un JSON à moitié écrit."""
    f = tmp_path / "sel.json"
    etat.enregistrer(7, 300, 50, 0.0, chemin=str(f))

    def json_dump_qui_echoue(*a, **kw):
        raise OSError("disque plein")

    monkeypatch.setattr(etat.json, "dump", json_dump_qui_echoue)
    with pytest.raises(OSError):
        etat.enregistrer(9, 300, 50, 0.0, chemin=str(f))

    assert etat.charger(str(f))["k"] == 7                  # l'ancien état a survécu
    restes = [p for p in os.listdir(tmp_path) if p.endswith(".tmp")]
    assert not restes, f"fichiers temporaires laissés derrière : {restes}"
