from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.paths import env_files, user_data_dir


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_files() or None,
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000
    market_data_mode: str = "replay"  # live | replay — live needs Kite on the server
    analyzer_url: str = "http://127.0.0.1:8000"
    database_url: str = ""
    redis_url: str = ""
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_access_token: str = ""
    nvidia_api_key: str = ""
    nvidia_nim_model: str = "nvidia/llama-3.1-nemotron-70b-instruct"
    news_enabled: bool = True
    archive_after_days: int = 14
    data_dir: Path | None = None

    @property
    def is_replay(self) -> bool:
        return self.market_data_mode.lower() == "replay"

    @property
    def kite_configured(self) -> bool:
        return bool(self.kite_api_key and self.kite_access_token)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    data = Path(s.data_dir) if s.data_dir else user_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    s.data_dir = data
    if not s.database_url:
        s.database_url = f"sqlite:///{(data / 'nifty_desk.sqlite').as_posix()}"
    return s
