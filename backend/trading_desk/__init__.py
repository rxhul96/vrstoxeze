"""Trading Desk integration — the analyzer's only path to a broker.

The analyzer's own modules (CVD, order flow, option chain, ICT, AI analysts, signal engine)
stay signal-only behind ``backend.safety.trading_disabled``. Everything that may place an
order lives in the vendored ``optionsdesk`` package (``desk/src``), which is mounted here as a
separate "Trading Desk" area: paper broker by default, ``ALLOW_LIVE_ORDERS=false``.

``optionsdesk`` is vendored rather than pip-installed so source checkouts, the in-place
Windows install and the PyInstaller bundle all resolve it the same way.
"""
from __future__ import annotations

import importlib.util
import sys

from backend.paths import desk_src_dir


def _bootstrap_optionsdesk() -> None:
    if importlib.util.find_spec("optionsdesk") is not None:
        return
    src = desk_src_dir()
    if (src / "optionsdesk" / "__init__.py").exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


_bootstrap_optionsdesk()
