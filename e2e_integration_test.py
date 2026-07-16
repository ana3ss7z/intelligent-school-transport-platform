#!/usr/bin/env python3
"""
Test d'intégration END-TO-END (par API) — chaîne complète.

Valide sur la stack RÉELLE :
  B1  clustering → busId propagé aux élèves
  G1  position GPS bus → MS12 calcule l'ETA → MS4 notifie (BUS_EN_ROUTE)
  G5  présence chauffeur → MS4 notifie le parent (ENFANT_A_BORD)
  G3  positions GPS incohérentes → MS11 détecte une anomalie live (VITESSE_EXCESSIVE)

Le script est AUTONOME : il crée un parent de test, l'affecte à un élève d'un bus, et enregistre
un device token (le seed n'a ni parentId ni token — sinon MS4 n'a personne à notifier).

Prérequis : stack lancée (docker-compose + osrm_meknes + start-all-ms.bat) + 300 élèves seedés
            + au moins 1 bus ACTIF dans MS1. Idéalement MS12 fraîchement démarré (cooldown ETA vide).
Usage :  python e2e_integration_test.py
"""
import sys
import time

import requests

GW = "http://localhost:8080"
MS11 = "http://localhost:8091"
ADMIN = {"email": "admin@transport.ma", "motDePasse": "Admin123!"}
PARENT = {"nom": "Parent E2E", "email": "parent.e2e@transport.ma", "motDePasse": "Parent123!", "role": "PARENT"}

_ok = _ko = 0


def check(name, cond, detail=""):
    global _ok, _ko
    print(f"  {'✅' if cond else '❌'} {name}" + (f" — {detail}" if detail else ""))
    _ok += cond; _ko += (not cond)
    return cond


def main():
    print("\n=== Test e2e intégration Transport Scolaire ===\n")
    try:
        token = requests.post(f"{GW}/api/auth/login", json=ADMIN, timeout=10).json()["token"]
    except Exception as e:
        print(f"❌ Stack injoignable ({e}). Lancer docker-compose + start-all-ms.bat."); sys.exit(1)
    H = {"Authorization": f"Bearer {token}"}
    print("Auth admin ✅")

    # ── Setup : parent de test + device token ──
    requests.post(f"{GW}/api/auth/register", json=PARENT, timeout=10)
    plog = requests.post(f"{GW}/api/auth/login", json={k: PARENT[k] for k in ("email", "motDePasse")}, timeout=10).json()
    pid, PH = plog["userId"], {"Authorization": f"Bearer {plog['token']}"}
    requests.post(f"{GW}/api/notifications/device-token", headers=PH,
                  json={"fcmToken": "e2e-fake-token", "plateforme": "ANDROID"}, timeout=10)
    print(f"Parent de test #{pid} + device token ✅\n")

    # ── B1 : clustering appliqué → busId ──
    print("[B1] Clustering + liaison groupe↔bus")
    r = requests.post(f"{GW}/api/clustering/production?appliquer=true", headers=H, timeout=180)
    check("POST /production", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        bb = r.json().get("bus_binding", {})
        check("liaison bus", bb.get("n_lies", 0) > 0, f"{bb.get('n_lies')} élèves, {bb.get('n_bus_actifs')} bus actifs")
    eleves = requests.get(f"{GW}/api/eleves", headers=H, timeout=30).json()
    avec_bus = [e for e in eleves if e.get("busId")]
    check("élèves avec busId", len(avec_bus) > 0, f"{len(avec_bus)}/{len(eleves)}")
    if not avec_bus:
        print("\n⚠️ Aucun bus ACTIF dans MS1 — impossible de continuer."); _resume()

    bus_id = avec_bus[0]["busId"]

    # ── G2 : tournées persistées (ordre de passage) ──
    print("\n[G2] Tournées persistées (ordre de passage)")
    rt = requests.post(f"{GW}/api/planification/tournees?persister=true", headers=H, timeout=180)
    check("POST /planification/tournees", rt.status_code == 200,
          f"HTTP {rt.status_code}" + (f", ordre_persiste={rt.json().get('ordre_persiste')}" if rt.status_code == 200 else ""))
    ordonnes = requests.get(f"{GW}/api/eleves/bus/{bus_id}", headers=H, timeout=15)
    if ordonnes.status_code == 200:
        rangs = [e.get("ordrePassage") for e in ordonnes.json()]
        check("élèves du bus ordonnés (ordrePassage)", any(r is not None for r in rangs), f"rangs={rangs[:6]}")
    else:
        check("GET /api/eleves/bus/{busId}", False, f"HTTP {ordonnes.status_code}")

    # Élève de TEST dédié (jamais un vrai élève) rattaché au parent de test + à un bus actif.
    # Il sera supprimé en fin de run → aucune donnée réelle n'est modifiée.
    rc = requests.post(f"{GW}/api/eleves", headers=H, timeout=10, json={
        "nom": "E2E", "prenom": "Test", "latitude": 33.905, "longitude": -5.575,
        "parentId": pid, "busId": bus_id})
    test_eid = rc.json().get("id") if rc.status_code in (200, 201) else None
    check("élève de test créé", test_eid is not None, f"id={test_eid}, bus={bus_id}")
    print(f"     élève de test #{test_eid} (bus {bus_id}) ← parent #{pid}\n")

    # ── G1 : GPS bus ~3 km → ETA ≤ 10 min → BUS_EN_ROUTE ──
    print("[G1] ETA temps réel")
    requests.post(f"{GW}/api/gps/position", headers=H, timeout=10, json={
        "cibleType": "BUS", "cibleId": bus_id, "latitude": 33.905, "longitude": -5.575,
        "vitesse": 40.0, "cap": 120.0, "precision": 5.0})
    time.sleep(6)

    # ── G5 : présence → ENFANT_A_BORD ──
    print("[G5] Présence enfant à bord")
    check("PATCH présence", requests.patch(f"{GW}/api/eleves/{test_eid}/presence?present=true", headers=H, timeout=10).status_code == 200)
    time.sleep(4)

    notifs = requests.get(f"{GW}/api/notifications", headers=H, timeout=15).json()
    lst = notifs if isinstance(notifs, list) else notifs.get("content", [])
    types = {n.get("type") for n in lst if n.get("parentId") == pid}
    check("notif BUS_EN_ROUTE (G1)", "BUS_EN_ROUTE" in types, "reçue" if "BUS_EN_ROUTE" in types else f"types={types}")
    check("notif ENFANT_A_BORD (G5)", "ENFANT_A_BORD" in types, "reçue" if "ENFANT_A_BORD" in types else f"types={types}")
    print("     (FCM dégradé/refus token = ECHEC en DB est normal ; la notif est bien enregistrée)")

    # ── G3 : anomalie GPS live ──
    print("\n[G3] Anomalie GPS live")
    for lat, lng in [(33.89, -5.55), (33.95, -5.62)]:
        requests.post(f"{GW}/api/gps/position", headers=H, timeout=10, json={
            "cibleType": "BUS", "cibleId": bus_id, "latitude": lat, "longitude": lng,
            "vitesse": 200.0, "cap": 90.0, "precision": 5.0})
        time.sleep(1)
    time.sleep(2)
    live = requests.get(f"{MS11}/api/analytique/live", timeout=10).json()
    kinds = [a.get("type") for a in live.get("anomalies", [])]
    check("anomalie live détectée", len(kinds) > 0, f"types={kinds[:3]}")

    # ── D1 : canal admin (alertes qualité + anomalie historisées) ──
    print("\n[D1] Canal de notification admin")
    # force un verdict qualité ≠ OK (rayon serré → dispersés↑) sans appliquer
    requests.post(f"{GW}/api/clustering/production?appliquer=false&rayon=1000", headers=H, timeout=180)
    time.sleep(4)
    alln = requests.get(f"{GW}/api/notifications", headers=H, timeout=15).json()
    alst = alln if isinstance(alln, list) else alln.get("content", [])
    admin_types = {n.get("type") for n in alst if n.get("sourceType") == "ADMIN"}
    check("alerte ALERTE_QUALITE (D1)", "ALERTE_QUALITE" in admin_types, "reçue" if "ALERTE_QUALITE" in admin_types else f"admin={admin_types}")
    check("alerte ANOMALIE_DETECTEE (D1)", "ANOMALIE_DETECTEE" in admin_types, "reçue" if "ANOMALIE_DETECTEE" in admin_types else f"admin={admin_types}")

    # Nettoyage : supprimer l'élève de test (aucune donnée réelle touchée)
    if test_eid:
        requests.delete(f"{GW}/api/eleves/{test_eid}", headers=H, timeout=10)
        print(f"\n(nettoyage : élève de test #{test_eid} supprimé)")

    _resume()


def _resume():
    print(f"\n=== Résultat : {_ok} ✅ / {_ko} ❌ ===")
    sys.exit(0 if _ko == 0 else 2)


if __name__ == "__main__":
    main()
