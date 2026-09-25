"""optionsdesk — governed NSE options auto-trading desk.

Paper trading by default. Live orders require ``ALLOW_LIVE_ORDERS=true`` *and* an explicit
per-order confirmation. Only NFO options can ever be traded; everything else is rejected in code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__version__ = "0.1.0"
__all__ = ["DeskConfig", "DeskEngine", "build_desk_router", "__version__"]

if TYPE_CHECKING:  # pragma: no cover
    from optionsdesk.api import build_desk_router
    from optionsdesk.config import DeskConfig
    from optionsdesk.engine import DeskEngine


def __getattr__(name: str) -> Any:
    # Lazy imports keep `import optionsdesk.risk_governor` free of FastAPI/broker dependencies.
    if name == "DeskConfig":
        from optionsdesk.config import DeskConfig

        return DeskConfig
    if name == "DeskEngine":
        from optionsdesk.engine import DeskEngine

        return DeskEngine
    if name == "build_desk_router":
        from optionsdesk.api import build_desk_router

        return build_desk_router
    raise AttributeError(name)
