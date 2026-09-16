# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Nifty Analyzer 2.0 (signal-only Command Desk)."""

from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("uvicorn") + collect_submodules("backend")

a = Analysis(
    ["desktop.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("frontend", "frontend"),
        ("backend/session/holidays.json", "backend/session"),
        ("assets/.env.default", "assets"),
    ],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="NiftyAnalyzer",
)
