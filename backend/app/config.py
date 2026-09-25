from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    datasets_path: str = "data/local_groups"
    upload_dir: str = "data/uploads"
    max_upload_bytes: int = 5 * 1024 * 1024  # 5 MB
    max_rows: int = 1000
    default_limit: int = 100
    query_timeout_ms: int = 5000
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
