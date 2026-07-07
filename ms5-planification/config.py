"""Configuration MS5-Planification (VRP) — pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    port: int = 8085
    osrm_url: str = "http://localhost:5000"
    ms2_url: str = "http://localhost:8082"

    # JWT — DOIT être identique à app.jwt.secret dans MS7 / Gateway
    jwt_secret: str = "transport_scolaire_secret_key_2026_super_long"

    # École = dépôt des tournées
    ecole_lat: float = 33.893
    ecole_lng: float = -5.5455

    # OR-Tools
    vrp_time_limit_s: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=())


settings = Settings()
