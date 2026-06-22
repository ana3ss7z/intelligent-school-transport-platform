# ================================================================
# OSRM Setup — Meknès, Maroc
# ================================================================
# OSRM calcule les vrais trajets routiers entre deux points GPS.
# On utilise l'image Docker officielle avec les données OSM du Maroc.
#
# ÉTAPES (une seule fois) :
# ================================================================

# 1. Créer le dossier pour les données OSM
mkdir -p osrm-data
cd osrm-data

# 2. Télécharger les données OSM du Maroc (fichier ~100MB)
#    Source : Geofabrik (données OpenStreetMap officielles)
curl -O https://download.geofabrik.de/africa/morocco-latest.osm.pbf

# 3. Pré-processing OSRM (3 étapes) — ~5-10 min
#    Utilise le profil "car" (voiture) pour les trajets de bus
docker run -t -v "$(pwd):/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/morocco-latest.osm.pbf
docker run -t -v "$(pwd):/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/morocco-latest.osrm
docker run -t -v "$(pwd):/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/morocco-latest.osrm

# 4. Lancer OSRM (port 5000)
docker run -d --name osrm_meknes \
  -p 5000:5000 \
  -v "$(pwd):/data" \
  ghcr.io/project-osrm/osrm-backend \
  osrm-routed --algorithm mld /data/morocco-latest.osrm

# 5. Tester OSRM (trajet Médina → Marjane)
curl "http://localhost:5000/route/v1/driving/-5.5547,33.8935;-5.5234,33.8821?overview=full&geometries=geojson"

# ================================================================
# Windows (PowerShell) — remplacer $(pwd) par le chemin absolu
# ================================================================
# Exemple :
# docker run -t -v "C:/Users/Anass/Desktop/SDIA/S9/PFE/transport-scolaire/osrm-data:/data" ...
#
# OU plus simple sur Windows : utiliser WSL pour ces commandes
# ================================================================
