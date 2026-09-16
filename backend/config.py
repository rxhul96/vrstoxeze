from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    market_data_mode: str = "live"  # live | replay
    analyzer_url: str = "http://127.0.0.1:8000"
    database_url: str = "sqlite:///data/nifty_desk.sqlite"
    redis_url: str = ""
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_access_token: str = ""
    nvidia_api_key: str = ""
    nvidia_nim_model: str = "nvidia/llama-3.1-nemotron-70b-instruct"
    news_enabled: bool = True
    archive_after_days: int = 14
    data_dir: Path = ROOT / "data"

    @property
    def is_replay(self) -> bool:
        return self.market_data_mode.lower() == "replay"

    @property
    def kite_configured(self) -> bool:
        return bool(self.kite_api_key and self.kite_access_token)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
