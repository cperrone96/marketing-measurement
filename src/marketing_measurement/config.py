"""Runtime configuration for local and PostgreSQL-backed environments."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load safe runtime settings from defaults or MM_-prefixed environment values."""

    database_url: str = "duckdb:///data/local/marketing.duckdb"
    data_dir: Path = Path("data")
    random_seed: int = 20260910
    model_config = SettingsConfigDict(env_prefix="MM_", env_file=".env")
