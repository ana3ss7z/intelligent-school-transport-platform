"""Configuration MS5-Planification (VRP) — pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    port: int = 8085
    osrm_url: str = "http://localhost:5000"
    ms2_url: str = "http://localhost:8082"
    # Route interne de MS1 : bus d'un chauffeur, pour le contrôle de portée du /tournee
    ms1_url: str = "http://localhost:8081"

    # Source de vérité des paramètres métier (MS13), appelée en direct — la route /internal
    # n'est pas publiée par la passerelle.
    ms13_url: str = "http://localhost:8092"

    # MS5 ne publie ni ne consomme d'événement métier ; il s'abonne uniquement à
    # `parametres.updated` pour recevoir les changements de configuration à chaud.
    # Sans courtier, il se rabat sur la relecture périodique.
    rabbitmq_url: str = "amqp://admin:admin123@localhost:5672/"
    exchange_name: str = "transport.exchange"

    # JWT — DOIT être identique à app.jwt.secret dans MS7 / Gateway
    jwt_secret: str = "transport_scolaire_secret_key_2026_super_long"

    # École = dépôt des tournées
    ecole_lat: float = 33.893
    ecole_lng: float = -5.5455

    # OR-Tools
    vrp_time_limit_s: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=())


settings = Settings()
