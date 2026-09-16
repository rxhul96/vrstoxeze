# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir for a self-contained Nifty Analyzer Windows app."""

from PyInstaller.utils.hooks import collect_all, collect_submodules

hidden = []
datas = [
    ("frontend", "frontend"),
    ("backend/session/holidays.json", "backend/session"),
    ("assets/.env.default", "assets"),
    ("assets/nifty.ico", "assets"),
    ("installer/LICENSE.txt", "."),
]
binaries = []

for pkg in (
    "uvicorn",
    "fastapi",
    "starlette",
    "pydantic",
    "pydantic_settings",
    "anyio",
    "websockets",
    "httptools",
    "h11",
    "watchfiles",
    "click",
    "webview",
    "backend",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hidden += h
    except Exception:
        hidden += collect_submodules(pkg)

hidden += [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "webview.platforms.edgechromium",
    "backend.main",
    "backend.paths",
]

a = Analysis(
    ["desktop.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hidden)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NiftyAnalyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon="assets/nifty.ico",
    version="installer/file_version_info.txt",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="NiftyAnalyzer",
)
