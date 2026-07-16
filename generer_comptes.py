#!/usr/bin/env python3
"""
Génération des comptes — parents (fratries), chauffeurs et bus — pour les 300 élèves seedés.

- Familles : regroupement par nom de famille + proximité géographique (fratries de 1 à 3 enfants).
  Même nom + proches = fratrie (1 parent) ; même nom mais éloignés = familles distinctes.
- Flotte : N_BUS bus ACTIF + autant de chauffeurs.
- Export : tous les identifiants (email/mot de passe/…) dans comptes_utilisateurs.csv + .json.

Appelle les services EN DIRECT (MS7:8087, MS1:8081, MS2:8082) avec le token admin pour éviter le
rate-limit de la Gateway. Prérequis : stack lancée + 300 élèves seedés.

Usage :  python generer_comptes.py
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
import unicodedata
from collections import defaultdict

import requests

# ── Config ───────────────────────────────────────────────────────────
MS7 = "http://localhost:8087"      # auth (register/login) — public
MS1 = "http://localhost:8081"      # bus — ADMIN
MS2 = "http://localhost:8082"      # eleves — ADMIN
ADMIN = {"email": "admin@transport.ma", "motDePasse": "Admin123!"}

N_BUS = 10
CAPACITE = 50
SIBLING_CAP = 3           # max enfants par famille
PROXIMITE_M = 600.0       # rayon max entre fratries (même nom)
PWD_PARENT = "Parent123!"
PWD_CHAUFFEUR = "Chauffeur123!"

CSV_PATH = "comptes_utilisateurs.csv"
JSON_PATH = "comptes_utilisateurs.json"

random.seed(42)
PRENOMS_ADULTES = ["Mohammed", "Fatima", "Ahmed", "Khadija", "Youssef", "Aicha", "Hassan",
                   "Nadia", "Said", "Latifa", "Karim", "Samira", "Rachid", "Naima",
                   "Omar", "Malika", "Abdelaziz", "Zineb", "Brahim", "Souad"]


# ── Helpers ──────────────────────────────────────────────────────────
def haversine_m(a, b) -> float:
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi = math.radians(b[0] - a[0]); dl = math.radians(b[1] - a[1])
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return "".join(c for c in s.lower() if c.isalnum())


def tel_ma() -> str:
    return "+2126" + "".join(str(random.randint(0, 9)) for _ in range(8))


def login_admin() -> str:
    r = requests.post(f"{MS7}/api/auth/login", json=ADMIN, timeout=10)
    r.raise_for_status()
    return r.json()["token"]


def register(nom, email, pwd, role, tel) -> int | None:
    """Crée un compte ; renvoie userId. Si l'email existe déjà, se connecte pour le récupérer."""
    body = {"nom": nom, "email": email, "motDePasse": pwd, "role": role, "telephone": tel}
    r = requests.post(f"{MS7}/api/auth/register", json=body, timeout=10)
    if r.status_code in (200, 201):
        return r.json()["userId"]
    # déjà existant → login
    rl = requests.post(f"{MS7}/api/auth/login", json={"email": email, "motDePasse": pwd}, timeout=10)
    if rl.status_code == 200:
        return rl.json()["userId"]
    print(f"  ⚠️ register/login échoué pour {email}: {r.status_code} {r.text[:80]}")
    return None


# ── Construction des familles (nom + proximité) ──────────────────────
def construire_familles(eleves: list[dict]) -> list[list[dict]]:
    # Tri déterministe (par id) → familles identiques quel que soit l'ordre renvoyé par MS2
    par_nom: dict[str, list[dict]] = defaultdict(list)
    for e in sorted(eleves, key=lambda e: e["id"]):
        par_nom[e.get("nom", "?")].append(e)

    familles: list[list[dict]] = []
    for nom in sorted(par_nom):
        restants = sorted(par_nom[nom], key=lambda e: e["id"])
        while restants:
            chef = restants.pop(0)
            fratrie = [chef]
            pos = (chef["latitude"], chef["longitude"])
            proches = sorted(restants, key=lambda e: haversine_m(pos, (e["latitude"], e["longitude"])))
            for e in proches:
                if len(fratrie) >= SIBLING_CAP:
                    break
                if haversine_m(pos, (e["latitude"], e["longitude"])) <= PROXIMITE_M:
                    fratrie.append(e); restants.remove(e)
            familles.append(fratrie)
    return familles


# ── Reset (optionnel) : purge des comptes générés orphelins via psql/docker ─────
def reset_comptes():
    import subprocess
    sql = ("DELETE FROM utilisateurs u WHERE u.role='PARENT' AND NOT EXISTS (SELECT 1 FROM eleves e WHERE e.parent_id=u.id);"
           "DELETE FROM utilisateurs u WHERE u.role='CHAUFFEUR' AND NOT EXISTS (SELECT 1 FROM bus b WHERE b.chauffeur_id=u.id);"
           "DELETE FROM utilisateurs u WHERE u.role='ADMIN' AND u.email <> 'admin@transport.ma';")
    try:
        subprocess.run(["docker", "exec", "transport_postgres", "psql", "-U", "transport_user",
                        "-d", "transport_scolaire", "-c", sql], check=True)
        print("🧹 Reset : comptes orphelins purgés.")
    except Exception as e:
        print(f"⚠️ Reset ignoré (docker/psql indisponible) : {e}")


# ── Programme principal ──────────────────────────────────────────────
def main():
    if "--reset" in sys.argv:
        reset_comptes()
    try:
        token = login_admin()
    except Exception as e:
        print(f"❌ Stack injoignable / login admin échoué ({e}). Lancer la stack d'abord."); sys.exit(1)
    H = {"Authorization": f"Bearer {token}"}
    print("Auth admin ✅")

    comptes_csv: list[dict] = []
    out = {"parents": [], "chauffeurs": [], "bus": []}

    # 1) Chauffeurs
    print(f"\nCréation de {N_BUS} chauffeurs…")
    chauffeurs = []
    for i in range(1, N_BUS + 1):
        prenom = PRENOMS_ADULTES[(i - 1) % len(PRENOMS_ADULTES)]
        nom = f"{prenom} (Chauffeur {i})"
        email = f"chauffeur{i}@transport.ma"
        tel = "+21266" + f"{i:07d}"
        uid = register(nom, email, PWD_CHAUFFEUR, "CHAUFFEUR", tel)
        if uid is None:
            continue
        chauffeurs.append({"userId": uid, "nom": nom, "email": email, "telephone": tel})
    print(f"  → {len(chauffeurs)} chauffeurs")

    # 2) Bus (chauffeur i ↔ bus i)
    print(f"Création de {len(chauffeurs)} bus ACTIF…")
    for i, ch in enumerate(chauffeurs, 1):
        matricule = f"{1000 + i}-A-50"
        body = {"matricule": matricule, "capacite": CAPACITE, "statut": "ACTIF", "chauffeurId": ch["userId"]}
        r = requests.post(f"{MS1}/api/bus", headers=H, json=body, timeout=10)
        bus_id = r.json().get("id") if r.status_code in (200, 201) else None
        if bus_id is None:  # peut-être déjà créé → retrouver via /actifs
            for b in requests.get(f"{MS1}/api/bus/actifs", timeout=10).json():
                if b.get("matricule") == matricule:
                    bus_id = b["id"]; break
        ch["busId"] = bus_id; ch["matricule"] = matricule
        out["bus"].append({"busId": bus_id, "matricule": matricule, "capacite": CAPACITE, "chauffeurId": ch["userId"]})
        comptes_csv.append({"role": "CHAUFFEUR", "userId": ch["userId"], "nom": ch["nom"], "email": ch["email"],
                            "motDePasse": PWD_CHAUFFEUR, "telephone": ch["telephone"],
                            "details": f"bus {matricule} (id={bus_id})"})
        out["chauffeurs"].append({**ch, "motDePasse": PWD_CHAUFFEUR})
    print(f"  → {len(out['bus'])} bus")

    # 3) Familles + parents
    eleves = requests.get(f"{MS2}/api/eleves", timeout=30).json()
    familles = construire_familles(eleves)
    multi = sum(1 for f in familles if len(f) > 1)
    print(f"\n{len(eleves)} élèves → {len(familles)} familles ({multi} avec ≥2 enfants). Création des parents…")

    n_liens = 0
    for idx, fratrie in enumerate(familles, 1):
        nom_fam = fratrie[0].get("nom", "Famille")
        cle = min(e["id"] for e in fratrie)          # clé de famille STABLE (plus petit id d'enfant)
        prenom_p = PRENOMS_ADULTES[cle % len(PRENOMS_ADULTES)]
        email = f"{slug(prenom_p)}.{slug(nom_fam)}.{cle}@famille.ma"   # unique et déterministe
        nom_parent = f"{prenom_p} {nom_fam}"
        tel = "+2126" + f"{cle:08d}"[-8:]            # déterministe → re-run = mêmes comptes
        pid = register(nom_parent, email, PWD_PARENT, "PARENT", tel)
        if pid is None:
            continue

        enfants = []
        for e in fratrie:
            body = {"nom": e["nom"], "prenom": e["prenom"], "latitude": e["latitude"],
                    "longitude": e["longitude"], "parentId": pid,
                    "busId": e.get("busId"), "groupeId": e.get("groupeId")}
            rp = requests.put(f"{MS2}/api/eleves/{e['id']}", headers=H, json=body, timeout=10)
            if rp.status_code == 200:
                n_liens += 1
            enfants.append({"id": e["id"], "prenom": e["prenom"], "nom": e["nom"]})

        comptes_csv.append({"role": "PARENT", "userId": pid, "nom": nom_parent, "email": email,
                            "motDePasse": PWD_PARENT, "telephone": tel,
                            "details": "enfants: " + ", ".join(f"{c['id']}:{c['prenom']}" for c in enfants)})
        out["parents"].append({"userId": pid, "nom": nom_parent, "email": email, "motDePasse": PWD_PARENT,
                               "telephone": tel, "enfants": enfants})
        if idx % 40 == 0:
            print(f"  … {idx}/{len(familles)} familles")
    print(f"  → {len(out['parents'])} parents créés, {n_liens} élèves liés")

    # 4) Export
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["role", "userId", "nom", "email", "motDePasse", "telephone", "details"])
        w.writeheader(); w.writerows(comptes_csv)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Terminé.")
    print(f"   {CSV_PATH}  ({len(comptes_csv)} comptes)")
    print(f"   {JSON_PATH}")
    print(f"   Parents={len(out['parents'])} · Chauffeurs={len(out['chauffeurs'])} · Bus={len(out['bus'])}")
    print(f"   Mots de passe : parents={PWD_PARENT} · chauffeurs={PWD_CHAUFFEUR}")


if __name__ == "__main__":
    main()
