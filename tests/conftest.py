import os
from pathlib import Path

os.environ.setdefault("MARKET_DATA_MODE", "replay")
os.environ.setdefault("DATABASE_URL", "sqlite:///data/test_nifty_desk.sqlite")
os.environ.setdefault("NEWS_ENABLED", "0")
# Trading Desk: isolated paper DB, never live. (Do not relax DESK_MARKET_HOURS_ONLY here — the
# vendored desk suite in desk/tests shares this process and asserts the default gate.)
os.environ.setdefault("DESK_DB_PATH", "data/test_desk.sqlite3")
os.environ.setdefault("ALLOW_LIVE_ORDERS", "false")
Path("data").mkdir(exist_ok=True)
Path("data/test_desk.sqlite3").unlink(missing_ok=True)
