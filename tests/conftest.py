import os
from pathlib import Path

os.environ.setdefault("MARKET_DATA_MODE", "replay")
os.environ.setdefault("DATABASE_URL", "sqlite:///data/test_nifty_desk.sqlite")
os.environ.setdefault("NEWS_ENABLED", "0")
Path("data").mkdir(exist_ok=True)
