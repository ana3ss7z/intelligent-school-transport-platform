"""Configuration MS11-analytique (pydantic-settings) — détection d'anomalies."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Réseau ───────────────────────────────────────────────────────
    port: int = 8091
    osrm_url: str = "http://localhost:5000"

    # Source de vérité des paramètres métier (MS13). Appelée en direct, PAS via la
    # passerelle : la route /internal n'y est pas publiée (elle renvoie les valeurs en clair).
    ms13_url: str = "http://localhost:8092"

    # JWT — DOIT être identique à app.jwt.secret dans MS7 / Gateway
    jwt_secret: str = "transport_scolaire_secret_key_2026_super_long"

    # ── Données (dataset d'anomalies PROPRE à MS11, généré par dataset_anomaly.py) ──
    dataset_path: str = "data/anomaly_dataset.csv"

    # ── Artefacts ────────────────────────────────────────────────────
    data_dir: str = "data"
    model_path: str = "data/anomaly_model.pkl"
    config_path: str = "data/anomaly_config.json"
    benchmark_path: str = "data/anomaly_benchmark.json"

    # ── Génération du dataset ────────────────────────────────────────
    seed: int = 42
    n_jours: int = 180
    incident_rate: float = 0.06       # proba d'incident par trajet (queue lourde hétérogène)

    # ── Détection ────────────────────────────────────────────────────
    contamination: float = 0.02       # proportion attendue d'anomalies (aligne le seuil)

    # ── Monitor GPS live (G3) : anomalies instantanées sur gps.bus.updated ──
    rabbitmq_url: str = "amqp://admin:admin123@localhost:5672/"
    exchange_name: str = "transport.exchange"
    seuil_arret_min: float = 5.0      # arrêt prolongé si immobile > N min
    seuil_vitesse_kmh: float = 90.0   # vitesse anormale au-delà (bus scolaire urbain)
    arret_rayon_m: float = 30.0       # déplacement en deçà duquel le bus est considéré immobile
    # Anti-rebond de la vitesse. 1 = comportement historique (un seul ping aberrant suffit à
    # lever une alerte critique) ; la déviation, elle, exige 2 pings depuis l'origine.
    vitesse_pings_consecutifs: int = 1

    # ── Déviation d'itinéraire (UC-8, 3ᵉ signal) : nécessite la route figée au démarrage du trajet (MS1) ──
    seuil_deviation_m: float = 250.0          # écart max toléré entre la position et la tournée planifiée
    deviation_pings_consecutifs: int = 2      # nb de pings hors couloir avant de déclencher (anti-faux positif)

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=()
    )


settings = Settings()
