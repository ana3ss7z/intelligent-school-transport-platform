"""Configuration MS11-analytique (pydantic-settings) — détection d'anomalies."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Réseau ───────────────────────────────────────────────────────
    port: int = 8091
    osrm_url: str = "http://localhost:5000"

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

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=()
    )


settings = Settings()
