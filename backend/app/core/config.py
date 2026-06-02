"""应用配置，通过环境变量加载。"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "icbc_platform"
    postgres_user: str = "icbc"
    postgres_password: str = ""

    jwt_secret: str = ""
    encryption_key: str = ""
    worker_api_key: str = ""

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    api_v1_prefix: str = "/api"
    app_base_url: str = "http://localhost"
    frontend_base_path: str = "/booking"
    cors_origins: str = ""
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
