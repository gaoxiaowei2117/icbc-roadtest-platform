"""worker 配置。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_base_url: str = "http://localhost:8000"
    worker_api_key: str = ""
    # 解密 ICBC 凭据的私钥（base64）。只放本地，云端永远没有。
    secret_private_key: str = ""

    poll_interval_seconds: int = 5
    max_concurrent: int = 3
    headless: bool = True
    log_level: str = "INFO"
    log_file: str = "worker.log"


settings = Settings()
