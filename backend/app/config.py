from functools import lru_cache
import json
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_cors_origins(value: Any) -> list[str]:
    """Accept JSON list, comma-separated string, or list (systemd-friendly)."""
    default = ["http://localhost:3000", "http://127.0.0.1:3000"]
    if value is None:
        return default
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return default
        if raw.startswith("["):
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError("CORS_ORIGINS JSON must be a list")
            return [str(v).strip() for v in parsed if str(v).strip()]
        return [part.strip() for part in raw.split(",") if part.strip()]
    raise TypeError(f"Unsupported CORS_ORIGINS type: {type(value)!r}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    datasets_path: str = "data/local_groups"
    upload_dir: str = "data/uploads"
    user_datasets_dir: str = "data/user_datasets"
    max_upload_bytes: int = 5 * 1024 * 1024  # 5 MB
    max_rows: int = 1000
    default_limit: int = 100
    query_timeout_ms: int = 5000
    max_query_chars: int = 100_000
    max_group_text_chars: int = 1_000_000
    max_relalg_statements: int = 32
    duckdb_memory_limit: str = "256MB"
    duckdb_threads: int = 2
    rate_limit_requests: int = 60
    rate_limit_window_seconds: float = 60.0
    expose_openapi: bool = False
    # NoDecode: systemd Environment=CORS_ORIGINS=https://host (not JSON)
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    api_root_path: str = "/api"
    owner_cookie_name: str = "relax_owner"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        return _parse_cors_origins(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
