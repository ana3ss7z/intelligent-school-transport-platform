#!/usr/bin/env python3
"""
Script de seeding — 300 élèves réels de Meknès
================================================
Usage :
    python seed_eleves_meknes.py              → génère seed_eleves_meknes.sql
    python seed_eleves_meknes.py --run        → insère directement via psycopg2
    python seed_eleves_meknes.py --http       → insère via API REST MS2
"""

import random, math, argparse, json
from datetime import datetime
from collections import Counter

DB_HOST, DB_PORT, DB_NAME = "localhost", 5432, "transport_scolaire"
DB_USER, DB_PASS          = "transport_user", "transport_pass"
API_BASE_URL  = "http://localhost:8082"
AUTH_BASE_URL = "http://localhost:8087"
ADMIN_EMAIL, ADMIN_PASSWORD = "admin@transport.local", "Admin123!"
TOTAL_ELEVES = 300

QUARTIERS = [
    {"nom": "Médina",           "lat": 33.8935, "lng": -5.5547, "weight": 25},
    {"nom": "Hamria",           "lat": 33.8978, "lng": -5.5489, "weight": 20},
    {"nom": "Zitoune",          "lat": 33.9012, "lng": -5.5523, "weight": 18},
    {"nom": "Ismailia",         "lat": 33.8876, "lng": -5.5612, "weight": 15},
    {"nom": "Marjane",          "lat": 33.8821, "lng": -5.5234, "weight": 22},
    {"nom": "Al Manzeh",        "lat": 33.8756, "lng": -5.5401, "weight": 20},
    {"nom": "Riad",             "lat": 33.8834, "lng": -5.5378, "weight": 18},
    {"nom": "Wislane",          "lat": 33.9067, "lng": -5.5456, "weight": 15},
    {"nom": "Borj Moulay Omar", "lat": 33.8923, "lng": -5.5689, "weight": 12},
    {"nom": "Mellah",           "lat": 33.8901, "lng": -5.5598, "weight": 14},
    {"nom": "Sidi Baba",        "lat": 33.8845, "lng": -5.5534, "weight": 16},
    {"nom": "Ain Karma",        "lat": 33.8712, "lng": -5.5312, "weight": 20},
    {"nom": "Nouzhat",          "lat": 33.8789, "lng": -5.5267, "weight": 18},
    {"nom": "Sidi Said",        "lat": 33.8956, "lng": -5.5445, "weight": 15},
    {"nom": "Hay Salam",        "lat": 33.8698, "lng": -5.5478, "weight": 12},
]

PRENOMS_GARCONS = ["Mohamed","Ahmed","Youssef","Omar","Ali","Hassan","Hamza",
    "Anas","Bilal","Ibrahim","Khalid","Rachid","Samir","Tarik","Karim",
    "Mehdi","Nabil","Adil","Zakaria","Soufiane","Ilyas","Ayoub","Othmane",
    "Abdellah","Abdelkarim"]
PRENOMS_FILLES = ["Fatima","Khadija","Aisha","Maryam","Zineb","Sara","Nadia",
    "Hajar","Salma","Imane","Dounia","Layla","Houda","Samira","Nora",
    "Yasmine","Rania","Hind","Loubna","Soukaina","Ghita","Kawtar",
    "Meriem","Oumaima","Chaimae"]
NOMS_FAMILLE = ["Benali","Benmoussa","Alaoui","Idrissi","Hassani","Benkirane",
    "Tazi","Filali","Chaoui","Bensouda","Amrani","Ziani","Berrada","Benomar",
    "Sqalli","Ouazzani","Lahlou","Chraibi","Benabdallah","Naciri","Rhazi",
    "Belkadi","Mansouri","Kettani","Benjelloun","Benbrahim","Senhaji","Rifai",
    "Benhaddou","Tahiri","Kasmi","Lamrani","Bouazza","Bennouna","Sebbata",
    "Ghali","Fassi","Drissi","Mernissi","Benabdeljalil"]

def variation_gps(lat, lng, rayon=350):
    lat_rad = math.radians(lat)
    m_lat = 111_320
    m_lng = 111_320 * math.cos(lat_rad)
    angle = random.uniform(0, 2 * math.pi)
    r = rayon * math.sqrt(random.uniform(0, 1))
    return (round(lat + (r * math.sin(angle)) / m_lat, 6),
            round(lng + (r * math.cos(angle)) / m_lng, 6))

def choisir_quartier():
    total = sum(q["weight"] for q in QUARTIERS)
    r, cumul = random.uniform(0, total), 0
    for q in QUARTIERS:
        cumul += q["weight"]
        if r <= cumul: return q
    return QUARTIERS[-1]

def generer_eleves(nb=TOTAL_ELEVES):
    random.seed(42)
    eleves = []
    for i in range(1, nb + 1):
        est_garcon = random.random() > 0.5
        prenom = random.choice(PRENOMS_GARCONS if est_garcon else PRENOMS_FILLES)
        nom = random.choice(NOMS_FAMILLE)
        q = choisir_quartier()
        lat, lng = variation_gps(q["lat"], q["lng"])
        eleves.append({"nom": nom, "prenom": prenom, "latitude": lat,
                        "longitude": lng, "quartier": q["nom"]})
    return eleves

def generer_sql(eleves):
    lines = [
        "-- ================================================================",
        "-- SEEDING : 300 Élèves — Meknès (coordonnées GPS réelles)",
        f"-- Généré le : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "-- ================================================================", "",
        "BEGIN;", "",
        "-- Décommenter pour vider la table avant insertion :",
        "-- TRUNCATE TABLE eleves RESTART IDENTITY CASCADE;", "",
        "INSERT INTO eleves (nom, prenom, latitude, longitude, parent_id, groupe_id, statut_presence)",
        "VALUES"
    ]
    rows = [f"  ('{e['nom']}', '{e['prenom']}', {e['latitude']}, {e['longitude']}, NULL, NULL, false)"
            for e in eleves]
    lines.append(",\n".join(rows) + ";")
    lines += ["", "COMMIT;", "", f"-- Total : {len(eleves)} élèves", "-- Répartition :"]
    for q, n in sorted(Counter(e["quartier"] for e in eleves).items(), key=lambda x: -x[1]):
        lines.append(f"--   {q:<25} {n:>3} élèves")
    return "\n".join(lines)

def seeder_via_api(eleves):
    import urllib.request, urllib.error
    login_data = json.dumps({"email": ADMIN_EMAIL, "motDePasse": ADMIN_PASSWORD}).encode()
    req = urllib.request.Request(f"{AUTH_BASE_URL}/api/auth/login", data=login_data,
                                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            token = json.loads(r.read())["token"]
        print(f"Token obtenu")
    except urllib.error.HTTPError as e:
        print(f"Login échoué : {e.code}"); return

    ok = errors = 0
    for i, e in enumerate(eleves, 1):
        payload = json.dumps({"nom": e["nom"], "prenom": e["prenom"],
                               "latitude": e["latitude"], "longitude": e["longitude"]}).encode()
        req = urllib.request.Request(f"{API_BASE_URL}/api/eleves", data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST")
        try:
            with urllib.request.urlopen(req): ok += 1
        except urllib.error.HTTPError as ex:
            errors += 1
        if i % 50 == 0:
            print(f"  [{i}/{len(eleves)}] {ok} OK, {errors} erreurs")
    print(f"Seeding terminé : {ok} insérés, {errors} erreurs")

def seeder_via_db(eleves):
    try: import psycopg2
    except ImportError: print("pip install psycopg2-binary"); return
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS)
    cur = conn.cursor()
    for e in eleves:
        cur.execute("INSERT INTO eleves (nom, prenom, latitude, longitude, parent_id, groupe_id, statut_presence) VALUES (%s,%s,%s,%s,NULL,NULL,false)",
                    (e["nom"], e["prenom"], e["latitude"], e["longitude"]))
    conn.commit(); cur.close(); conn.close()
    print(f"{len(eleves)} élèves insérés en base.")

def main():
    parser = argparse.ArgumentParser(description="Seeding 300 élèves Meknès")
    parser.add_argument("--run",  action="store_true", help="Insertion via psycopg2")
    parser.add_argument("--http", action="store_true", help="Insertion via API REST")
    parser.add_argument("--nb",   type=int, default=TOTAL_ELEVES)
    args = parser.parse_args()

    eleves = generer_eleves(args.nb)
    print(f"{len(eleves)} élèves générés\n")
    for q, n in sorted(Counter(e["quartier"] for e in eleves).items(), key=lambda x: -x[1]):
        print(f"  {q:<25} {n:>3} élèves")

    if args.http:        seeder_via_api(eleves)
    elif args.run:       seeder_via_db(eleves)
    else:
        sql = generer_sql(eleves)
        with open("seed_eleves_meknes.sql", "w", encoding="utf-8") as f: f.write(sql)
        print(f"\nFichier SQL généré : seed_eleves_meknes.sql")
        print(f"psql -h {DB_HOST} -U {DB_USER} -d {DB_NAME} -f seed_eleves_meknes.sql")
        print(f"# ou via Docker :")
        print(f"docker exec -i transport_postgres psql -U {DB_USER} -d {DB_NAME} < seed_eleves_meknes.sql")

if __name__ == "__main__":
    main()
