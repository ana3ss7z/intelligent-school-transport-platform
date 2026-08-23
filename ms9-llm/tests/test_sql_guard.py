"""
Suite de sécurité du garde SQL (MS9 Phase B — NL2SQL admin).

`sql_guard.py` est une liste noire par expression régulière : du code court, critique, et qui
n'avait **aucun test**. Or c'est la couche que le jury regardera en premier, puisque c'est elle
qui se trouve entre un modèle de langage et une base de production.

Le corpus vit dans `corpus_sql.py`. Chaque cas déclare le comportement attendu **du garde seul** —
y compris les cas où le garde laisse passer et où c'est PostgreSQL qui doit arrêter. Ces cas-là ne
sont pas des échecs : ils sont la démonstration exécutable que la défense est en profondeur.

    pytest ms9-llm/tests -q
"""
import re

import pytest

from corpus_sql import CORPUS
from sql_guard import SqlRejected, valider_et_normaliser
from config import settings


def _ids(categorie: str) -> list:
    return [pytest.param(c, id=c["id"]) for c in CORPUS if c["categorie"] == categorie]


def _verifier(cas: dict) -> None:
    if cas["attendu"] == "accepte":
        sortie = valider_et_normaliser(cas["sql"])
        assert sortie, "le garde a renvoyé une requête vide"
    else:
        with pytest.raises(SqlRejected):
            valider_et_normaliser(cas["sql"])


# ── 1. Le garde ne casse pas l'usage normal ──────────────────────────────────
@pytest.mark.parametrize("cas", _ids("legitime"))
def test_requete_legitime_acceptee(cas):
    _verifier(cas)


# ── 2. Le garde bloque ce qu'il annonce bloquer ──────────────────────────────
@pytest.mark.parametrize("cas", _ids("attaque"))
def test_attaque_rejetee(cas):
    _verifier(cas)


# ── 3. Ce que le garde NE voit pas — déféré à PostgreSQL, et documenté ───────
@pytest.mark.parametrize("cas", _ids("contournement"))
def test_contournement_passe_le_garde(cas):
    """Ces requêtes franchissent le garde applicatif. C'est le rôle `ms9_readonly`,
    la transaction READ ONLY et `statement_timeout` qui les arrêtent — pas la regex."""
    _verifier(cas)


# ── 4. Le coût du garde : des requêtes légitimes refusées ────────────────────
@pytest.mark.parametrize("cas", _ids("faux_positif"))
def test_faux_positif_documente(cas):
    """Sur-blocage connu. Le test fige le comportement : si un jour il change,
    c'est une décision, pas une dérive silencieuse."""
    _verifier(cas)


# ── 5. Le LIMIT : la seule transformation que le garde s'autorise ────────────
def test_limit_ajoute_quand_absent():
    sortie = valider_et_normaliser("SELECT nom FROM eleves")
    assert sortie.endswith(f"LIMIT {settings.sql_default_limit}")


def test_limit_existant_non_double():
    sortie = valider_et_normaliser("SELECT nom FROM eleves LIMIT 10")
    assert len(re.findall(r"\blimit\b", sortie, re.IGNORECASE)) == 1
    assert sortie.rstrip().endswith("LIMIT 10")


def test_limit_imbrique_empeche_le_cap_externe():
    """Conséquence mesurée du contournement `limit_imbrique` : un LIMIT en sous-requête
    suffit à désarmer l'ajout du LIMIT externe. Le cap effectif redevient `sql_max_rows`."""
    sortie = valider_et_normaliser(
        "SELECT e.nom FROM eleves e JOIN (SELECT id FROM bus LIMIT 1) b ON e.bus_id = b.id"
    )
    assert not sortie.rstrip().endswith(f"LIMIT {settings.sql_default_limit}")


def test_point_virgule_terminal_retire():
    assert ";" not in valider_et_normaliser("SELECT COUNT(*) FROM bus;")


# ── 6. Le nettoyage des commentaires ne doit pas fabriquer de faille ─────────
def test_commentaire_ne_recolle_pas_les_mots():
    """`SEL/**/ECT` ne doit pas devenir `SELECT` : le commentaire est remplacé par un
    espace, jamais par du vide. Sinon la vérification du premier mot serait contournable."""
    with pytest.raises(SqlRejected):
        valider_et_normaliser("SEL/**/ECT * FROM eleves")


def test_mot_cle_interdit_scinde_par_commentaire_reste_inoffensif():
    """`pg_sl/**/eep(10)` échappe à la liste noire, mais devient du SQL invalide :
    la scission qui contourne le filtre détruit aussi l'attaque."""
    sortie = valider_et_normaliser("SELECT pg_sl/**/eep(10)")
    assert "pg_sleep" not in sortie.lower()


def test_commentaire_bloc_non_ferme_laisse_le_mot_cle_visible():
    """Un `/*` jamais refermé n'est pas retiré : le mot-clé reste exposé à la liste noire."""
    with pytest.raises(SqlRejected):
        valider_et_normaliser("SELECT 1 /* DROP TABLE eleves")
