"""Configuration MS12-Prediction (pydantic-settings) — calqué sur MS6."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Réseau ───────────────────────────────────────────────────────
    port: int = 8088
    osrm_url: str = "http://localhost:5000"
    ms3_url: str = "http://localhost:8083"
    ms2_url: str = "http://localhost:8082"

    # ── Pipeline ETA temps réel (G1) : MS3 gps.bus.updated → ETA → MS4 ─
    rabbitmq_url: str = "amqp://admin:admin123@localhost:5672/"
    exchange_name: str = "transport.exchange"
    eta_alert_min: float = 10.0        # seuil "arrivée imminente" (min) → alerte parents
    ecole_lat: float = 33.893          # destination (arrivée à l'école)
    ecole_lng: float = -5.5455
    eta_check_throttle_s: float = 20.0 # recalcule l'ETA d'un bus au plus toutes les N s
    eta_alert_cooldown_s: float = 1800.0  # ré-alerte au plus 1×/30 min par bus

    # ── Fournisseurs de contexte (features en production) ────────────
    weather_provider: str = "open-meteo"                         # open-meteo | off
    weather_url: str = "https://api.open-meteo.com/v1/forecast"  # gratuit, sans clé
    traffic_provider: str = "heuristic"                          # heuristic | tomtom
    tomtom_key: str = ""                                         # optionnel (free-tier)
    history_path: str = "data/eta_history.csv"                   # historique réel (bootstrap = dataset)

    # JWT — DOIT être identique à app.jwt.secret dans MS7 / Gateway
    jwt_secret: str = "transport_scolaire_secret_key_2026_super_long"

    # ── Artefacts (relatifs au dossier du service) ───────────────────
    data_dir: str = "data"
    dataset_path: str = "data/eta_dataset.csv"
    model_path: str = "data/eta_model.pkl"
    config_path: str = "data/eta_config.json"
    benchmark_path: str = "data/benchmark_summary.json"

    # ── Génération du dataset ────────────────────────────────────────
    seed: int = 42
    n_jours: int = 180                 # nombre de jours d'école générés
    date_debut: str = "2025-09-08"     # rentrée scolaire (lundi)
    incident_rate: float = 0.05        # proba d'incident par trajet (queue lourde)
    bruit_pct: float = 0.10            # écart-type relatif du bruit irréductible
    temps_embarquement_s: float = 4.0  # dwell par montée/descente (secondes)
    test_jours: int = 30               # derniers jours d'école réservés au test (split temporel)

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=()
    )


settings = Settings()
