from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoringWeights(BaseSettings):
    w1_winrate_mapa: float = Field(1.0, alias="W1_WINRATE_MAPA")
    w2_counter_score: float = Field(1.0, alias="W2_COUNTER_SCORE")
    w3_sinergia: float = Field(0.8, alias="W3_SINERGIA")
    w4_pickrate_relativo: float = Field(0.5, alias="W4_PICKRATE_RELATIVO")
    w5_ban_risk: float = Field(0.6, alias="W5_BAN_RISK")
    w6_counterable: float = Field(0.7, alias="W6_COUNTERABLE")
    w7_personal_proficiency: float = Field(1.2, alias="W7_PERSONAL_PROFICIENCY")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://brawl:brawl@localhost:5432/brawl_draft"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 21600

    supercell_api_key: str = ""
    supercell_api_base: str = "https://api.brawlstars.com/v1"

    # Fuente de estadísticas que usa el job de ingesta (run_daily).
    # "mock" = datos sintéticos; "brawlify" = scraper real (hoy bloqueado por Cloudflare).
    stats_source: str = "mock"

    # Token para el endpoint /admin/bootstrap (poblar DB en la nube). Vacío = deshabilitado.
    admin_token: str = ""

    brawlify_base_url: str = "https://brawlify.com"
    brawlify_user_agent: str = "BrawlDraftAssistant/0.1"
    brawlify_rate_limit_seconds: float = 1.0

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def weights(self) -> ScoringWeights:
        return ScoringWeights()


@lru_cache
def get_settings() -> Settings:
    return Settings()
