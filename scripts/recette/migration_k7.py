#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lot 3 — retour à k=7 bus, mesuré des deux côtés.

Pourquoi
--------
L'hystérésis de MS6 (piège n° 19) garde le `k` en place tant qu'il tient, pour éviter que
chaque inscription redistribue toute l'école. C'est le bon comportement — mais elle a ancré
le système sur une partition à **9 bus** produite avant le correctif, et cette partition
s'est dégradée : un groupe est tombé à **9 élèves sur 50 places** (18 % de remplissage),
soit un bus et un chauffeur mobilisés pour neuf enfants, pendant qu'un autre en porte 47.

`etat.charger()` renvoie `None` si le fichier de mémoire est absent → `k_precedent=None`
(`clustering.py:169`) → l'hystérésis est désarmée et `choisir_k` tranche à neuf. Le piège
n° 19 documente qu'après correctif, **k=7 sort sur 30 permutations sur 30**.

Ce script mesure AVANT, désarme l'hystérésis, relance, mesure APRÈS, et publie le churn —
le nombre d'élèves qui changent de bus, c'est-à-dire ce que les familles subissent.

Usage : python scripts/recette/migration_k7.py
Sortie : scripts/recette/resultats/migration_k7.json
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import time
from collections import Counter

import requests

for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RACINE = pathlib.Path(__file__).resolve().parents[2]
SORTIE = RACINE / "scripts" / "recette" / "resultats" / "migration_k7.json"
ETAT = RACINE / "ms6-clustering" / "data" / "last_selection.json"
GW, MS2_INT, MS6 = "http://localhost:8080", "http://localhost:8082/internal/eleves", "http://localhost:8086"


def roster() -> list[dict]:
    return requests.get(MS2_INT, timeout=40).json()


def photo(eleves: list[dict]) -> dict:
    """Affectation élève→bus + distribution des tailles de groupe."""
    grp = Counter(e.get("groupeId") for e in eleves)
    tailles = {g: n for g, n in grp.items() if g not in (None, 999)}
    return {
        "n_eleves": len(eleves),
        "k": len(tailles),
        "tailles": dict(sorted(tailles.items())),
        "min": min(tailles.values()) if tailles else None,
        "max": max(tailles.values()) if tailles else None,
        "sous_remplis_moins_20": sorted(g for g, n in tailles.items() if n < 20),
        "affectation": {e["id"]: e.get("busId") for e in eleves},
    }


def afficher(titre: str, p: dict) -> None:
    print(f"\n{titre}")
    print(f"  k = {p['k']} groupes · {p['n_eleves']} élèves · min={p['min']} max={p['max']}")
    for g, n in p["tailles"].items():
        alerte = "   ← SOUS-REMPLI" if n < 20 else ""
        print(f"    groupe {g:>2} : {n:>3} élèves  {'#' * max(1, n // 2)}{alerte}")


def main() -> int:
    print("\n=== Lot 3 — retour à k=7 ===")
    TA = requests.post(f"{GW}/api/auth/login",
                       json={"email": "admin@transport.ma", "motDePasse": "Admin123!"},
                       timeout=20).json()["token"]
    H = {"Authorization": f"Bearer {TA}"}

    # ── 1. état de départ ──
    avant = photo(roster())
    afficher("AVANT — partition en place", avant)

    etat_avant = json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else None
    print(f"\n  mémoire d'hystérésis : {etat_avant}")

    # ── 2. désarmer l'hystérésis ──
    if ETAT.exists():
        sauvegarde = ETAT.with_suffix(".json.bak-avant-migration-k7")
        shutil.copy2(ETAT, sauvegarde)
        ETAT.unlink()
        print(f"  mémoire sauvegardée puis retirée → {sauvegarde.name}")
    else:
        print("  (aucune mémoire à retirer)")

    # ── 3. relancer le clustering de production ──
    print("\n  POST /api/clustering/production?appliquer=true …")
    r = requests.post(f"{GW}/api/clustering/production?appliquer=true", headers=H, timeout=300)
    if r.status_code != 200:
        print(f"  ÉCHEC HTTP {r.status_code} — {r.text[:300]}")
        return 2
    res = r.json()
    q = res.get("quality", {})
    print(f"  → k = {res.get('k')} · silhouette {res.get('silhouette')} "
          f"· dispersés {res.get('n_disperses')} · verdict {q.get('niveau')}")
    if q.get("raisons"):
        for motif in q["raisons"]:
            print(f"      · {motif}")

    time.sleep(2)
    apres = photo(roster())
    afficher("APRÈS — nouvelle partition", apres)

    # ── 4. churn : ce que les familles subissent ──
    communs = set(avant["affectation"]) & set(apres["affectation"])
    deplaces = [i for i in communs if avant["affectation"][i] != apres["affectation"][i]]
    churn = 100 * len(deplaces) / len(communs) if communs else 0.0
    print(f"\nCHURN — {len(deplaces)}/{len(communs)} élèves changent de bus ({churn:.1f} %)")
    print("  (c'est le coût réel de la migration, à annoncer aux familles)")

    # ── 5. restaurer l'ordre de passage, sinon le simulateur zigzague en silence ──
    print("\n  POST /api/planification/tournees?persister=true …")
    rt = requests.post(f"{GW}/api/planification/tournees?sens=matin&persister=true",
                       headers=H, timeout=600)
    ordre_ok = 0
    if rt.status_code == 200:
        t = rt.json()
        print(f"  → {t.get('n_tournees', '?')} tournées · {t.get('distance_totale_m', '?')} m "
              f"· gain moyen {t.get('gain_moyen_%', '?')} %")
        ordre_ok = sum(1 for e in roster() if e.get("ordrePassage") is not None)
        print(f"  → ordrePassage renseigné sur {ordre_ok}/{apres['n_eleves']} élèves")
    else:
        print(f"  ÉCHEC HTTP {rt.status_code} — {rt.text[:200]}")

    # ── 6. verdict qualité publié par le service ──
    qual = requests.get(f"{MS6}/api/clustering/quality", timeout=40).json()
    dv = qual.get("dernier_verdict") or {}
    mes = dv.get("mesures", {})
    print(f"\nVERDICT QUALITÉ : {dv.get('niveau')} "
          f"· silhouette {mes.get('silhouette')} · compacité max {mes.get('compacite_max_m')} m "
          f"· taille_max {mes.get('taille_max')} · faisable {mes.get('faisable')}")

    etat_apres = json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else None
    print(f"nouvelle mémoire d'hystérésis : {etat_apres}")

    # ── 7. tableau comparatif ──
    print("\n" + "=" * 62)
    print(f"{'':22} {'AVANT':>16} {'APRÈS':>16}")
    print("-" * 62)
    print(f"{'nombre de bus':22} {avant['k']:>16} {apres['k']:>16}")
    print(f"{'plus petit groupe':22} {avant['min']:>16} {apres['min']:>16}")
    print(f"{'plus grand groupe':22} {avant['max']:>16} {apres['max']:>16}")
    print(f"{'groupes < 20 élèves':22} {len(avant['sous_remplis_moins_20']):>16} "
          f"{len(apres['sous_remplis_moins_20']):>16}")
    moy_a = avant['n_eleves'] / avant['k']; moy_p = apres['n_eleves'] / apres['k']
    print(f"{'remplissage moyen':22} {moy_a:>15.1f}  {moy_p:>15.1f}")
    print(f"{'taux de remplissage':22} {100*moy_a/50:>15.0f}% {100*moy_p/50:>15.0f}%")
    print("=" * 62)

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    for p in (avant, apres):
        p.pop("affectation", None)  # trop volumineux pour le rapport
    SORTIE.write_text(json.dumps({
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "avant": avant, "apres": apres,
        "etat_hysteresis_avant": etat_avant, "etat_hysteresis_apres": etat_apres,
        "churn_eleves": len(deplaces), "churn_pct": round(churn, 2),
        "ordre_passage_renseigne": ordre_ok,
        "verdict_qualite": dv,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDétail : {SORTIE}")
    return 0 if apres["k"] == 7 else 1


if __name__ == "__main__":
    sys.exit(main())
