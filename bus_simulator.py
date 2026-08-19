#!/usr/bin/env python3
"""
Simulateur de Bus v2 (data-driven) — Transport Scolaire Meknès
==============================================================
Contrairement au v1 (3 bus fictifs sur des circuits inventés), ce simulateur est
PILOTÉ PAR LES VRAIES DONNÉES du back et exerce toute la chaîne temps réel :

  1. Login MS7 (admin) via Gateway  → JWT
  2. GET /api/bus/actifs            → la vraie flotte active
  3. GET /api/eleves/bus/{id}       → les élèves du bus DANS l'ordre de passage (MS5/G2)
     → si `ordrePassage` est vide (MS5 jamais lancé), l'ordre serait ARBITRAIRE : on
       appelle alors MS5 /tournee (TSP OR-Tools) qui le calcule et le persiste. Le bus
       roule donc toujours sur la tournée optimisée. `--optimiser` force le recalcul.
  4. Trajet réel = école → arrêt 1 → 2 → … → n → école, chaque tronçon suivant la vraie
     route OSRM (pas de ligne droite), converge vers l'école
     → déclenche G1 (MS12 : ETA ≤ 10 min → notif parents) en fin de tournée
  5. (--presence) à chaque arrêt atteint : PATCH /api/eleves/{id}/presence
     → déclenche G5 (« enfant à bord » → notif au bon parent) — matin=montée, soir=descente
  6. (--anomalies) injecte des pics de vitesse (> 90 km/h)
     → déclenche G3 (MS11 monitor GPS live : VITESSE_EXCESSIVE)

Usage :
  pip install requests
  python bus_simulator.py                       # toute la flotte, matin, sans effets
  python bus_simulator.py --presence            # + montées d'élèves (G5)
  python bus_simulator.py --presence --anomalies# + anomalies de vitesse (G3)
  python bus_simulator.py --bus 8               # un seul bus
  python bus_simulator.py --max-bus 3           # limiter à 3 bus (démo lisible)
  python bus_simulator.py --sens soir --presence# tournée du soir (dépose)
  python bus_simulator.py --optimiser           # recalculer les tournées MS5 avant de rouler
  python bus_simulator.py --loop --interval 0.5 # boucle, plus fluide
  python bus_simulator.py --verbose             # log chaque point GPS

Arrêt : Ctrl+C (géré proprement) — ou Ctrl+Pause (Ctrl+Break) sous Windows.
"""

import argparse
import math
import random
import sys
import threading
import time
from datetime import datetime

import requests

# Console Windows (cp1252) : forcer UTF-8 pour les emojis/accents
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ─── Configuration ────────────────────────────────────────────────────────────

GATEWAY_URL = "http://localhost:8080"
OSRM_URL    = "http://localhost:5000"
ADMIN_EMAIL = "admin@transport.ma"
ADMIN_PASS  = "Admin123!"

ECOLE = {"nom": "École Al Massira", "lat": 33.893, "lng": -5.5455}  # dépôt (départ/arrivée)

VITESSE_KMH_NORMALE  = 40.0
VITESSE_KMH_ANOMALIE = 110.0   # > seuil MS11 (90) → G3 VITESSE_EXCESSIVE
PROBA_ANOMALIE_LEG   = 0.15    # proba d'un pic de vitesse par tronçon (mode --anomalies)

stop_event = threading.Event()  # signal d'arrêt global (Ctrl+C)


# ─── Auth ─────────────────────────────────────────────────────────────────────

def get_token() -> str:
    print(f"[Auth] Login {ADMIN_EMAIL} via Gateway…")
    resp = requests.post(
        f"{GATEWAY_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "motDePasse": ADMIN_PASS},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json().get("token")
    if not token:
        raise ValueError(f"Token absent : {resp.json()}")
    print("[Auth] ✅ Token obtenu")
    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── Chargement des données réelles ───────────────────────────────────────────

def get_bus_actifs(token: str) -> list[dict]:
    resp = requests.get(f"{GATEWAY_URL}/api/bus/actifs", headers=auth_headers(token), timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_eleves_ordonnes(token: str, bus_id: int) -> list[dict]:
    """Élèves d'un bus DANS l'ordre de passage (endpoint trié MS2/G2)."""
    resp = requests.get(f"{GATEWAY_URL}/api/eleves/bus/{bus_id}", headers=auth_headers(token), timeout=10)
    resp.raise_for_status()
    eleves = resp.json()
    # garde uniquement ceux avec coords valides, dans l'ordre renvoyé
    return [e for e in eleves if e.get("latitude") is not None and e.get("longitude") is not None]


# ─── Tournée optimisée (MS5) ──────────────────────────────────────────────────

def optimiser_tournee_ms5(token: str, groupe_id: int, sens: str) -> dict | None:
    """Tournée optimale d'un groupe via MS5 (TSP OR-Tools sur durées OSRM) + persistance MS2."""
    try:
        resp = requests.post(
            f"{GATEWAY_URL}/api/planification/tournee",
            params={"groupeId": groupe_id, "sens": sens, "persister": "true"},
            headers=auth_headers(token), timeout=180,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  ⚠️  MS5 /tournee a échoué : {e}")
        return None


def assurer_ordre_optimise(token: str, bus: dict, eleves: list[dict], args) -> list[dict]:
    """
    Garantit que le bus roule sur la tournée OPTIMISÉE, pas dans un ordre arbitraire.

    `/api/eleves/bus/{id}` trie par `ordrePassage` — mais si MS5 n'a jamais tourné, ce champ est
    NULL pour tout le monde : PostgreSQL place les NULL en fin de tri ASC et l'ordre restant est
    celui, non déterministe, de la table. Le bus zigzaguerait alors entre les arrêts **sans que
    rien ne le signale**. On détecte ce cas et on déclenche MS5, qui réécrit `ordrePassage`.
    """
    bus_id = bus["id"]
    groupe = eleves[0].get("groupeId")
    sans_ordre = [e for e in eleves if e.get("ordrePassage") is None]

    if not sans_ordre and not args.optimiser:
        print(f"[Bus {bus_id}] ✅ tournée déjà optimisée (ordre MS5 persisté)")
        return eleves
    if groupe is None:
        print(f"[Bus {bus_id}] ⚠️  aucun groupe (clustering MS6 non appliqué) — ordre arbitraire")
        return eleves

    raison = ("réoptimisation demandée (--optimiser)" if args.optimiser
              else f"{len(sans_ordre)}/{len(eleves)} élèves sans ordre de passage")
    print(f"[Bus {bus_id}] 🧭 {raison} → MS5 /tournee (TSP OR-Tools, durées OSRM)…")
    res = optimiser_tournee_ms5(token, groupe, args.sens)
    if res is None:
        print(f"[Bus {bus_id}] ⚠️  MS5 indisponible — le bus roulera dans un ordre NON optimisé")
        return eleves

    gain = res.get("gain_vs_baseline_%")
    detail = f"{res.get('distance_m', 0) / 1000:.1f} km · {res.get('duree_min', 0):.0f} min"
    if gain is not None:
        detail += f" · gain {gain:.1f} % vs ordre naïf"
    print(f"[Bus {bus_id}] ✅ tournée optimisée : {detail}")
    return get_eleves_ordonnes(token, bus_id)  # relit l'ordre fraîchement persisté par MS5


# ─── OSRM ─────────────────────────────────────────────────────────────────────

def get_route_osrm(depart: dict, arrivee: dict) -> list[tuple[float, float]]:
    """Trajet routier réel entre deux points → liste de (lat, lng)."""
    url = (
        f"{OSRM_URL}/route/v1/driving/"
        f"{depart['lng']},{depart['lat']};{arrivee['lng']},{arrivee['lat']}"
        f"?overview=full&geometries=geojson&steps=false"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok":
            return interpoler_ligne_droite(depart, arrivee)
        coords = data["routes"][0]["geometry"]["coordinates"]
        return [(c[1], c[0]) for c in coords]  # [lng,lat] → (lat,lng)
    except Exception:
        return interpoler_ligne_droite(depart, arrivee)


def interpoler_ligne_droite(depart: dict, arrivee: dict, nb_points: int = 20) -> list[tuple[float, float]]:
    pts = []
    for i in range(nb_points + 1):
        t = i / nb_points
        pts.append((depart["lat"] + t * (arrivee["lat"] - depart["lat"]),
                    depart["lng"] + t * (arrivee["lng"] - depart["lng"])))
    return pts


def calculer_cap(lat1, lng1, lat2, lng2) -> float:
    lat1_r, lat2_r, dlng_r = math.radians(lat1), math.radians(lat2), math.radians(lng2 - lng1)
    x = math.sin(dlng_r) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlng_r)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


# ─── Publication GPS + présence ───────────────────────────────────────────────

def publier_position(token, bus_id, lat, lng, cap, vitesse) -> bool:
    try:
        resp = requests.post(
            f"{GATEWAY_URL}/api/gps/position",
            json={"cibleType": "BUS", "cibleId": bus_id,
                  "latitude": round(lat, 6), "longitude": round(lng, 6),
                  "vitesse": vitesse, "cap": round(cap, 1), "precision": 5.0},
            headers=auth_headers(token), timeout=5,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"  [Bus {bus_id}] ❌ publication GPS : {e}")
        return False


def marquer_presence(token, eleve_id, present: bool) -> bool:
    try:
        resp = requests.patch(
            f"{GATEWAY_URL}/api/eleves/{eleve_id}/presence?present={str(present).lower()}",
            headers=auth_headers(token), timeout=5,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False


# ─── Simulation d'un bus ──────────────────────────────────────────────────────

def simuler_bus(token, bus, eleves, args):
    bus_id = bus["id"]
    groupe = eleves[0].get("groupeId") if eleves else None
    # Points de passage : école → élèves (ordre) → école
    waypoints = [ECOLE] + [{"nom": f"{e['prenom']} {e['nom']}", "lat": e["latitude"],
                            "lng": e["longitude"], "eleve": e} for e in eleves] + [ECOLE]

    print(f"[Bus {bus_id}] 🚌 groupe {groupe} · {len(eleves)} arrêts · sens {args.sens}")

    tour = 0
    while not stop_event.is_set():
        tour += 1
        if args.loop:
            print(f"[Bus {bus_id}] 🔄 tour {tour}")

        for leg in range(len(waypoints) - 1):
            if stop_event.is_set():
                return
            a, b = waypoints[leg], waypoints[leg + 1]
            points = get_route_osrm(a, b)
            # un pic de vitesse éventuel sur ce tronçon (mode --anomalies)
            idx_anomalie = (random.randint(0, len(points) - 1)
                            if args.anomalies and len(points) > 1 and random.random() < PROBA_ANOMALIE_LEG
                            else -1)

            for j, (lat, lng) in enumerate(points):
                if stop_event.is_set():
                    return
                cap = calculer_cap(lat, lng, *points[j + 1]) if j < len(points) - 1 else 0.0
                vitesse = VITESSE_KMH_ANOMALIE if j == idx_anomalie else VITESSE_KMH_NORMALE
                ok = publier_position(token, bus_id, lat, lng, cap, vitesse)
                if args.verbose:
                    ts = datetime.now().strftime("%H:%M:%S")
                    flag = "  ⚡ANOMALIE-VITESSE" if j == idx_anomalie else ""
                    print(f"  [{ts}] Bus {bus_id} {'✅' if ok else '❌'} ({lat:.5f},{lng:.5f}) {vitesse:.0f}km/h{flag}")
                if idx_anomalie >= 0 and j == idx_anomalie and not args.verbose:
                    print(f"  [Bus {bus_id}] ⚡ pic de vitesse {VITESSE_KMH_ANOMALIE:.0f} km/h → G3")
                if stop_event.wait(args.interval):  # sommeil interruptible
                    return

            # Arrivée à un arrêt-élève (waypoints[1..n]) → présence (G5)
            if 1 <= leg + 1 <= len(eleves):
                e = eleves[leg]
                if args.presence:
                    present = args.sens == "matin"   # matin=montée, soir=descente
                    if marquer_presence(token, e["id"], present):
                        verbe = "à bord" if present else "déposé"
                        print(f"  [Bus {bus_id}] 🧒 {e['prenom']} {e['nom']} {verbe} (arrêt {leg + 1}/{len(eleves)}) → G5")

        print(f"[Bus {bus_id}] 🏁 tournée terminée (retour école → G1 ETA)")
        if not args.loop:
            return
        if stop_event.wait(5):
            return


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Simulateur Bus v2 (data-driven) — Meknès")
    p.add_argument("--interval", type=float, default=1.0, help="secondes entre positions (défaut 1.0)")
    p.add_argument("--loop", action="store_true", help="boucle infinie")
    p.add_argument("--bus", type=int, default=None, help="simuler un seul bus (id actif)")
    p.add_argument("--max-bus", type=int, default=None, help="limiter le nombre de bus (démo)")
    p.add_argument("--sens", choices=["matin", "soir"], default="matin", help="ramassage (matin) / dépose (soir)")
    p.add_argument("--optimiser", action="store_true",
                   help="forcer la réoptimisation MS5 avant de rouler (par défaut : seulement si l'ordre manque)")
    p.add_argument("--presence", action="store_true", help="marquer la présence aux arrêts (G5)")
    p.add_argument("--anomalies", action="store_true", help="injecter des pics de vitesse (G3)")
    p.add_argument("--verbose", action="store_true", help="log chaque point GPS")
    args = p.parse_args()

    print("=" * 64)
    print("  🚌 Simulateur Bus v2 (data-driven) — Transport Scolaire Meknès")
    print(f"  Gateway {GATEWAY_URL} · sens={args.sens} · presence={args.presence} · anomalies={args.anomalies}")
    print("=" * 64)

    try:
        token = get_token()
    except Exception as e:
        print(f"❌ Login impossible ({e}) — vérifier MS7 + Gateway")
        return

    try:
        bus_actifs = get_bus_actifs(token)
    except Exception as e:
        print(f"❌ Impossible de charger les bus actifs ({e}) — vérifier MS1")
        return

    if args.bus is not None:
        bus_actifs = [b for b in bus_actifs if b["id"] == args.bus]
        if not bus_actifs:
            print(f"❌ Bus {args.bus} introuvable parmi les actifs")
            return
    if args.max_bus:
        bus_actifs = bus_actifs[: args.max_bus]

    # Charger les élèves ordonnés de chaque bus, ignorer les bus vides
    plans = []
    for b in bus_actifs:
        eleves = get_eleves_ordonnes(token, b["id"])
        if not eleves:
            print(f"[Bus {b['id']}] ⏭️  aucun élève affecté (ordre non planifié) — ignoré")
            continue
        plans.append((b, assurer_ordre_optimise(token, b, eleves, args)))

    if not plans:
        print("❌ Aucun bus avec des élèves ordonnés. Lance d'abord le clustering (appliquer=true) "
              "puis MS5 /tournees?persister=true pour remplir ordrePassage.")
        return

    print(f"[Init] {len(plans)} bus simulés : {[b['id'] for b, _ in plans]}\n")

    threads = []
    for b, eleves in plans:
        t = threading.Thread(target=simuler_bus, args=(token, b, eleves, args), daemon=True)
        threads.append(t)
        t.start()
        time.sleep(0.3)  # démarrage échelonné (évite le burst sur la Gateway)

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\n⏹️  Arrêt demandé — on stoppe les bus proprement…")
        stop_event.set()
        for t in threads:
            t.join(timeout=3)
    print("✅ Simulation terminée")


if __name__ == "__main__":
    main()
