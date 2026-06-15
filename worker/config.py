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

    # road.py 抢号配置
    road_config_path: str = "./config.yml"
    booking_timeout_seconds: int = 600   # run() 限时循环上限，须 < backend RUNNING_TIMEOUT_MINUTES(15min)
    booking_poll_seconds: int = 30       # 没号时两轮 job() 之间的间隔

    # 系统级 Gmail（收 OTP），由运维配在 worker .env，不每用户存
    gmail_email: str = ""
    gmail_app_password: str = ""

    poll_interval_seconds: int = 5
    max_concurrent: int = 3
    headless: bool = True
    log_level: str = "INFO"
    log_file: str = "worker.log"


settings = Settings()
