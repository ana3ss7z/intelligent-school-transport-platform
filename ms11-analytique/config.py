"""Configuration MS11-analytique (pydantic-settings) — détection d'anomalies."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Réseau ───────────────────────────────────────────────────────
    port: int = 8091
    osrm_url: str = "http://localhost:5000"

    # JWT — DOIT être identique à app.jwt.secret dans MS7 / Gateway
    jwt_secret: str = "transport_scolaire_secret_key_2026_super_long"

    # ── Données (dataset ETA de MS12 : trajets + label incident_type) ──
    eta_dataset_path: str = "../ms12-prediction/data/eta_dataset.csv"

    # ── Artefacts ────────────────────────────────────────────────────
    data_dir: str = "data"
    model_path: str = "data/anomaly_model.pkl"
    config_path: str = "data/anomaly_config.json"
    benchmark_path: str = "data/anomaly_benchmark.json"

    # ── Détection ────────────────────────────────────────────────────
    seed: int = 42
    contamination: float = 0.02       # proportion attendue d'anomalies (aligne le seuil)

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=()
    )


settings = Settings()
