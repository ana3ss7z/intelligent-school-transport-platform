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


def attendre(predicat, secondes=40, pas=2.5):
    """Attend qu'une condition devienne vraie, au lieu de lire une seule fois.

    Les etapes precedentes lisaient les notifications apres un `sleep` fixe. Or la chaine
    traverse RabbitMQ et plusieurs services : sa latence varie de 1 a 20 s selon la charge, et
    le systeme produit des centaines de notifications par minute quand le pipeline ETA tourne.
    Une lecture unique attrapait donc le resultat ou le manquait, sans que rien ne distingue
    les deux cas. On attend desormais activement, avec une borne franche.
    """
    fin = time.time() + secondes
    dernier = None
    while time.time() < fin:
        dernier = predicat()
        if dernier:
            return dernier
        time.sleep(pas)
    return dernier


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

    # On préfère un bus qui n'a PAS reçu d'alerte BUS_EN_ROUTE récemment : MS12 impose un
    # cooldown de 30 min par bus (ETA_ALERT_COOLDOWN_S), et sans cette précaution G1 échoue
    # non parce que la chaîne est cassée, mais parce que le bus a déjà été annoncé. C'est le
    # même piège que l'anti-spam de MS11 : un garde-fou anti-rafale n'est pas un défaut, mais
    # un test qui l'ignore mesure autre chose que ce qu'il croit.
    bus_candidats = [e["busId"] for e in avec_bus]
    try:
        _j = requests.get(f"{GW}/api/notifications?page=0&size=400&tri=dateEnvoi&sens=desc",
                          headers=H, timeout=30).json()
        _lst = _j.get("content", _j if isinstance(_j, list) else [])
        recents = {n.get("sourceId") for n in _lst if n.get("type") == "BUS_EN_ROUTE"}
    except Exception:
        recents = set()
    bus_id = next((b for b in bus_candidats if b not in recents), bus_candidats[0])
    if bus_id in recents:
        print(f"     (tous les bus ont été annoncés récemment — G1 peut échouer sur le cooldown)")

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
    #
    # Le contexte est FIGÉ pendant cette étape. MS12 alerte quand l'ETA passe sous 10 min ;
    # or la même position donnait 9,73 min par temps nuageux et trafic dense, et 6,95 min par
    # beau temps — le résultat dépendait donc de la météo du jour, pas du code. C'est le
    # piège n° 31 : un test dont le verdict change avec le temps qu'il fait ne teste rien.
    # On utilise le mode « contexte manuel » de MS13, prévu exactement pour cela, puis on
    # restaure la valeur d'origine. Marge obtenue : ~3 min sous le seuil.
    # Trois garde-fous de MS12 rendaient ce test dépendant du hasard. Aucun n'est un défaut :
    # ce sont des protections légitimes. Mais un test qui les ignore mesure autre chose que ce
    # qu'il croit — c'est le piège n° 31.
    #
    #   1. Le CONTEXTE. La même position donnait 9,73 min par temps nuageux et trafic dense,
    #      6,95 min par beau temps. Le verdict dépendait de la météo, pas du code. On fige le
    #      contexte avec le mode « manuel » de MS13, prévu exactement pour cela.
    #   2. Le COOLDOWN de 30 min par bus : un bus déjà annoncé ne réalerte pas. Sur une session
    #      active, presque tous les bus y sont. On l'abaisse au minimum autorisé (60 s).
    #   3. Le BUS RÉEL de l'élève. Le recalcul automatique du regroupement peut le déplacer
    #      entre sa création et le ping (constaté : créé sur le bus 16, déplacé sur le 18).
    #      Pinger le bus d'origine touche alors des parents qui ne sont plus les siens.
    #
    # Tous les réglages sont restaurés ensuite.
    reglages_avant = {}
    A_FIGER = {"ms12.contexte_mode": "manuel",
               "ms12.eta_alert_cooldown_s": "60",
               "ms12.eta_check_throttle_s": "5"}
    try:
        params = requests.get(f"{GW}/api/parametres", headers=H, timeout=15).json()
        reglages_avant = {x["cle"]: x.get("valeur") for x in params if x["cle"] in A_FIGER}
        requests.put(f"{GW}/api/parametres", headers=H, timeout=15, json={"valeurs": A_FIGER})
        time.sleep(3)   # propagation à chaud MS13 → MS12
    except Exception as e:
        print(f"     (réglages non figés : {e} — G1 redevient dépendant du contexte)")

    # On ping le bus choisi plus haut pour son cooldown VIDE — pas celui de l'élève de test.
    # Le recalcul automatique déplace l'élève d'un bus à l'autre entre sa création et le ping
    # (constaté : créé sur le 16, déplacé sur le 18), et ce bus d'arrivée a, lui, souvent déjà
    # été annoncé. Suivre l'élève revenait donc à retomber systématiquement dans le cooldown.
    # G1 teste la chaîne GPS → ETA → notification ; le rattachement au bon parent est couvert
    # par G5, qui emprunte le même chemin MS4.
    bus_eta = bus_id

    print(f"[G1] ETA temps réel (contexte figé, bus {bus_eta})")

    def _publications_eta():
        """Nombre de `eta.bus.arriving` publiés — le maillon MS12 → MS4, mesuré à la source."""
        try:
            d = requests.get("http://localhost:15672/api/queues/%2F/ms4.eta.arriving.queue",
                             auth=("admin", "admin123"), timeout=15).json()
            return d.get("message_stats", {}).get("publish", 0)
        except Exception:
            return None

    def _journal(taille=400):
        try:
            j = requests.get(f"{GW}/api/notifications?page=0&size={taille}&tri=dateEnvoi&sens=desc",
                             headers=H, timeout=20).json()
            return j if isinstance(j, list) else j.get("content", [])
        except Exception:
            return []

    def _max_id():
        ids = [n.get("id") for n in _journal(50) if n.get("id") is not None]
        return max(ids) if ids else 0

    def _nouvelle_notif_bus(bus, depuis_id):
        """Une BUS_EN_ROUTE POSTÉRIEURE au repère, pour ce bus.

        On compare des identifiants, pas des comptes : le journal est une fenêtre glissante
        (les 400 plus récentes) et le système en produit assez pour que les lignes d'avant
        en sortent entre les deux lectures. Un compte stable ne prouverait alors rien.
        """
        return any(n.get("type") == "BUS_EN_ROUTE" and n.get("sourceId") == bus
                   and (n.get("id") or 0) > depuis_id for n in _journal())

    # Le compteur de la file est GLOBAL : il monte dès qu'un bus quelconque déclenche une
    # alerte. Seule la notification portant `sourceId == ce bus` prouve la chaîne pour LUI.
    id_avant = _max_id()
    requests.post(f"{GW}/api/gps/position", headers=H, timeout=10, json={
        "cibleType": "BUS", "cibleId": bus_eta, "latitude": 33.905, "longitude": -5.575,
        "vitesse": 40.0, "cap": 120.0, "precision": 5.0})

    trouve = attendre(lambda: _nouvelle_notif_bus(bus_eta, id_avant) or None, secondes=45)
    check("GPS → MS12 → MS4 : BUS_EN_ROUTE historisée pour les parents du bus",
          bool(trouve),
          f"notification postérieure à #{id_avant} pour le bus {bus_eta}"
          if trouve else f"aucune notification après #{id_avant} (bus {bus_eta})")

    # ── G5 : présence → ENFANT_A_BORD ──
    print("[G5] Présence enfant à bord")
    check("PATCH présence", requests.patch(f"{GW}/api/eleves/{test_eid}/presence?present=true", headers=H, timeout=10).status_code == 200)
    time.sleep(4)

    # On lit avec le jeton du PARENT, pas le journal d'administration. Ce dernier est paginé
    # (25 lignes par défaut, les plus récentes) et le système produit assez de notifications
    # — alertes d'anomalie, ETA de toute la flotte — pour enterrer celle du parent de test en
    # quelques secondes. `/mes-notifications` est déjà scopé au demandeur : c'est la lecture
    # que fait la vraie application parent, et elle ne dépend pas du volume global.
    def _types_parent():
        try:
            return {n.get("type") for n in
                    requests.get(f"{GW}/api/notifications/mes-notifications",
                                 headers=PH, timeout=15).json()}
        except Exception:
            return set()

    types = attendre(lambda: (_types_parent() if "ENFANT_A_BORD" in _types_parent()
                              else None)) or _types_parent()
    check("notif ENFANT_A_BORD (G5)", "ENFANT_A_BORD" in types, "reçue" if "ENFANT_A_BORD" in types else f"types={types}")
    print("     (FCM dégradé/refus token = ECHEC en DB est normal ; la notif est bien enregistrée)")

    # restauration des réglages MS12
    if reglages_avant:
        requests.put(f"{GW}/api/parametres", headers=H, timeout=15,
                     json={"valeurs": {k: v for k, v in reglages_avant.items() if v}})

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
    # Le journal d'administration est paginé (25 lignes par défaut, les plus récentes). Quand
    # le pipeline ETA tourne, il produit assez de notifications pour enterrer les alertes du
    # canal admin en quelques secondes : on demande une page large ET on attend activement,
    # au lieu de lire une fois après un délai fixe.
    def _admin_types():
        try:
            j = requests.get(f"{GW}/api/notifications?page=0&size=400&tri=dateEnvoi&sens=desc",
                             headers=H, timeout=20).json()
            lst = j if isinstance(j, list) else j.get("content", [])
            return {n.get("type") for n in lst if n.get("sourceType") == "ADMIN"}
        except Exception:
            return set()

    attendu = {"ALERTE_QUALITE", "ANOMALIE_DETECTEE"}
    admin_types = attendre(lambda: (_admin_types() if attendu <= _admin_types() else None)) \
        or _admin_types()
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
