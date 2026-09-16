"""Install / runtime paths. Works from source, venv install, and PyInstaller."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "NiftyAnalyzer"


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Read-only files shipped with the app (frontend, holidays, defaults)."""
    if frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def install_root() -> Path:
    """Writable/code root. Source checkout, LOCALAPPDATA install, or exe dir."""
    if frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
        d = Path(base) / APP_NAME
    else:
        d = Path.home() / ".local" / "share" / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def frontend_dir() -> Path:
    bundled = bundle_root() / "frontend"
    if (bundled / "index.html").exists():
        return bundled
    return install_root() / "frontend"


def env_files() -> tuple[str, ...]:
    """User .env wins over install .env, which wins over bundled defaults."""
    candidates = [
        user_data_dir() / ".env",
        install_root() / ".env",
        bundle_root() / ".env.default",
        bundle_root() / "assets" / ".env.default",
    ]
    return tuple(str(p) for p in candidates if p.exists())
