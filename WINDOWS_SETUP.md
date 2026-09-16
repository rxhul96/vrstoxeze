# Install Nifty Analyzer 2.0 (Command Desk)

Windows install for the **signal-only** NIFTY Institutional Command Desk.
This build **cannot** place, modify, or cancel Zerodha orders.

If you still have **1.3.x**, uninstall it first (Settings → Apps → Nifty Analyzer)
so Start Menu shortcuts point at 2.0.

## Install (recommended)

From a checkout of this repo (PowerShell):

```powershell
cd D:\path\to\vrstoxeze
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

Optional Desktop icon:

```powershell
.\install.ps1 -DesktopShortcut
```

Then open **Nifty Analyzer** from the Start Menu.

| Item | Location |
|------|----------|
| App files | `%LOCALAPPDATA%\NiftyAnalyzer` |
| Config + SQLite session | `%APPDATA%\NiftyAnalyzer` |
| Start Menu | Nifty Analyzer |
| Uninstall | `powershell -File %LOCALAPPDATA%\NiftyAnalyzer\uninstall.ps1` |

First launch uses `MARKET_DATA_MODE=replay` so the desk comes up immediately.
Edit `%APPDATA%\NiftyAnalyzer\.env` to switch to live Kite (read-only):

```
MARKET_DATA_MODE=live
KITE_API_KEY=...
KITE_API_SECRET=...
```

In [Kite Connect](https://developers.kite.trade/) set **Redirect URL** to:

```
http://127.0.0.1:8000/kite/callback
```

Log in **inside the app** (server callback). The API secret never leaves this PC.

## Run from the repo (no install)

```powershell
.\run.ps1
```

or double-click `Nifty Analyzer.bat`.

Needs Python 3.12+ on PATH (`py` or `python`).

## Build Setup.exe (optional)

Needs [Inno Setup 6](https://jrsoftware.org/isinfo.php) and Python 3.12.

```powershell
.\build_windows.ps1
```

Output: `dist\windows\NiftyAnalyzer-Setup-2.0.0.exe`

That exe is a per-user install (no admin). Same data folder as `install.ps1`.

## Docker (always-on server)

```powershell
cd deploy
copy ..\assets\.env.default .env
docker compose up --build
```

Then visualization-only desktop:

```powershell
$env:ANALYZER_URL = "http://127.0.0.1:8000"
python desktop.py --client
```

Closing the desktop does not stop Docker collection.

## What 2.0 adds

- SIGNAL-ONLY MODE permanently (no order ticket, no broker execution)
- Docked Command Desk (chart + virtualized option chain + signal card)
- ESTIMATED CVD, OI heatmap, PCR terminal, ICT, news decay, frozen score
- Session replay from 09:15 if you open the app mid-day
- Health bar, Kite login-required / signals paused
