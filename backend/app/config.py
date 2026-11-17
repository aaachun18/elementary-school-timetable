from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    postgres_db: str
    postgres_user: str
    postgres_password: str

    # 帳號改版: the mail sent when an account is created. No smtp_host ->
    # the mail is written to the backend log instead (development / tests).
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "no-reply@timetable.local"
    smtp_use_tls: bool = True
    # The login page the mail points to.
    app_login_url: str = "http://localhost:5173/login"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
