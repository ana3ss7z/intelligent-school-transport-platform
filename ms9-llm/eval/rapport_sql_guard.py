"""
Transforme le corpus de `tests/corpus_sql.py` en chiffres.

Les tests disent « le garde se comporte comme prévu ». Ce script dit **de combien** : taux de
blocage des attaques, taux de faux positifs, nombre de cas délibérément déférés à PostgreSQL.
C'est cette forme-là qui va dans le mémoire — un tableau, pas une affirmation.

    python eval/rapport_sql_guard.py

Écrit `eval/resultats/sql_guard.json` et affiche le tableau Markdown.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

from corpus_sql import CATEGORIES, CORPUS          # noqa: E402
from sql_guard import SqlRejected, valider_et_normaliser  # noqa: E402

LIBELLE = {
    "legitime": "Requêtes légitimes",
    "attaque": "Attaques",
    "contournement": "Contournements (déférés à PostgreSQL)",
    "faux_positif": "Faux positifs (coût du garde)",
}


def observer(sql: str) -> tuple[str, str]:
    """Retourne (comportement, détail) du garde applicatif seul."""
    try:
        return "accepte", valider_et_normaliser(sql)
    except SqlRejected as e:
        return "rejete", str(e)


def main() -> int:
    lignes = []
    for cas in CORPUS:
        obtenu, detail = observer(cas["sql"])
        lignes.append({**cas, "obtenu": obtenu, "detail": detail,
                       "conforme": obtenu == cas["attendu"]})

    par_cat = {c: [l for l in lignes if l["categorie"] == c] for c in CATEGORIES}
    non_conformes = [l for l in lignes if not l["conforme"]]

    attaques = par_cat["attaque"]
    bloquees = [l for l in attaques if l["obtenu"] == "rejete"]
    legitimes = par_cat["legitime"]
    passees = [l for l in legitimes if l["obtenu"] == "accepte"]

    resume = {
        "n_cas": len(lignes),
        "n_non_conformes": len(non_conformes),
        "attaques_total": len(attaques),
        "attaques_bloquees": len(bloquees),
        "taux_blocage_attaques_%": round(100 * len(bloquees) / max(1, len(attaques)), 1),
        "legitimes_total": len(legitimes),
        "legitimes_acceptees": len(passees),
        "faux_positifs_connus": len(par_cat["faux_positif"]),
        "contournements_deferes_postgres": len(par_cat["contournement"]),
        "par_categorie": {c: len(v) for c, v in par_cat.items()},
    }

    sortie = RACINE / "eval" / "resultats"
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "sql_guard.json").write_text(
        json.dumps({"resume": resume, "cas": lignes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n## Garde SQL — corpus d'évaluation\n")
    print("| Catégorie | Cas | Comportement du garde applicatif |")
    print("|---|--:|---|")
    attendu_txt = {
        "legitime": "laisse passer",
        "attaque": "rejette",
        "contournement": "**laisse passer** — PostgreSQL arrête",
        "faux_positif": "rejette (à tort)",
    }
    for c in CATEGORIES:
        print(f"| {LIBELLE[c]} | {len(par_cat[c])} | {attendu_txt[c]} |")
    print(f"\n**{len(lignes)} cas · {len(non_conformes)} écart(s) au comportement attendu.**")
    print(f"Blocage des attaques : {resume['attaques_bloquees']}/{resume['attaques_total']} "
          f"({resume['taux_blocage_attaques_%']} %)")
    print(f"Requêtes légitimes préservées : {resume['legitimes_acceptees']}/{resume['legitimes_total']}")

    if non_conformes:
        print("\n### Écarts\n")
        for l in non_conformes:
            print(f"- `{l['id']}` : attendu **{l['attendu']}**, obtenu **{l['obtenu']}** — {l['detail']}")
        return 1

    print("\n### Détail des contournements (la démonstration de la défense en profondeur)\n")
    for l in par_cat["contournement"]:
        print(f"- **`{l['id']}`** — {l['note']}")
    print("\n### Détail des faux positifs (le coût, mesuré)\n")
    for l in par_cat["faux_positif"]:
        print(f"- **`{l['id']}`** — {l['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
