from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ms2_url: str = "http://localhost:8082"
    ms1_url: str = "http://localhost:8081"
    osrm_url: str = "http://localhost:5000"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    exchange_name: str = "transport.exchange"
    port: int = 8086

    # JWT — doit correspondre exactement à app.jwt.secret dans MS7
    jwt_secret: str = "changeme"

    # ── Stratégie de production (clustering capacitaire routier) ──────────
    bus_capacity: int = 50          # capacité d'un bus (paramètre métier extensible)
    rayon_max_m: float = 0.0        # distance max élève→médoïde (m) ; 0 = désactivé (paramètre ajustable)
    use_road_distance: bool = True  # OSRM (vrai réseau) ; repli euclidien si indisponible
    use_road_for_auto: bool = False # recalcul auto (RabbitMQ) : euclidien par défaut (rapide)
    epsg_metric: int = 32630        # UTM 30N (Meknès) — projection planaire en mètres
    min_silhouette: float = 0.50    # garde-fou qualité (CDC) pour la piste exploratoire
    k_margin: int = 3               # marge de bus explorée au-delà de ⌈N/capacité⌉ (Pareto)
    kmedoids_iters: int = 6

    # ── Garde-fou qualité (dynamique, calibré sur notre point réel ~0.43, PAS 0.5) ──
    quality_baseline_path: str = "data/quality_baseline.json"          # référence roulante (écrite au runtime)
    quality_frozen_config_path: str = "notebooks/production_config.json"  # bootstrap de la référence
    quality_sil_drop_rel: float = 0.15    # chute relative de silhouette tolérée vs référence
    quality_sil_drop_abs: float = 0.05    # chute absolue mini pour déclencher (évite le bruit)
    quality_sil_floor_rel: float = 0.75   # plancher = 0.75 × silhouette gelée (~0.325), anti-effondrement
    quality_comp_inc_rel: float = 0.25    # hausse relative de compacité max tolérée
    quality_disperses_inc: int = 15       # hausse absolue de dispersés tolérée vs référence

    # ── Hyperparamètres legacy (K-Means / DBSCAN exploratoires) ──────────
    k_min: int = 3
    k_max: int = 5
    dbscan_eps: float = 1.5         # km (Haversine) — endpoint /dbscan legacy
    dbscan_min_samples: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
