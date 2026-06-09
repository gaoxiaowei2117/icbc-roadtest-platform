"""应用配置，通过环境变量加载。"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "icbc_platform"
    postgres_user: str = "icbc"
    postgres_password: str = ""

    jwt_secret: str = ""
    # 非对称封装加密：后端只持公钥（只能加密）；私钥仅在本地 worker。
    secret_public_key: str = ""
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

    # 任务卡死 reaper（T2）：扫描间隔 + running 超时阈值
    reaper_interval_seconds: int = 60
    running_timeout_minutes: int = 15

    # 速率限制（T10）：登录/注册防暴力枚举
    rate_limit_enabled: bool = True
    auth_rate_limit: str = "5/minute"

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    database_url_override: str = Field(default="", alias="DATABASE_URL")

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
