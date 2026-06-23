"""Root runtime settings."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings shared by backend modules."""

    config_dir: Path = Path("config")
    data_dir: Path = Path("data")
    duckdb_path: Path = Path("data/duckdb/analytics.duckdb")
    chroma_dir: Path = Path("data/chroma")
    run_mode: Literal["dev", "local-live", "replay", "offline"] = "dev"
    deepseek_api_key: str | None = None
    tushare_token: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DAB_",
        extra="ignore",
    )
