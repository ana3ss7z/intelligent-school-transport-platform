from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ms2_url: str = "http://localhost:8082"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    exchange_name: str = "transport.exchange"
    port: int = 8086

    # JWT — doit correspondre exactement à app.jwt.secret dans MS7
    jwt_secret: str = "changeme"

    # K-Means
    k_min: int = 3
    k_max: int = 5

    # DBSCAN Haversine — eps en km
    dbscan_eps: float = 1.5
    dbscan_min_samples: int = 5

    class Config:
        env_file = ".env"


settings = Settings()