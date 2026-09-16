# Nifty Institutional Command Desk

Signal-only NIFTY 50 market intelligence: an always-on server plus a visualization desktop.

**THE HUMAN ALWAYS MAKES THE FINAL TRADING DECISION. NEVER AUTOMATICALLY TRADE.**

Windows users: **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)** — double-click **`INSTALL.bat`** in this folder. That installs in place and puts a **Nifty Analyzer** app on the Desktop.

```
ZERODHA KITE (read-only)
        ↓
CLOUD MARKET SERVER (this repo: FastAPI + Postgres/SQLite + Redis)
        ↓
QUANT ENGINES → AI ANALYSTS → MASTER ANALYST → SIGNAL ENGINE
        ↓
DESKTOP TERMINAL
        ↓
HUMAN DECISION
```

There is no path `signal → broker → order`. Kite is used only for LTP, OHLC, history, instruments, quotes, OI, volume, depth, and WebSocket ticks.

## Install on Windows

Double-click **`INSTALL.bat`** in this folder. The app stays here (venv in `.\.venv`). You get a Desktop shortcut named **Nifty Analyzer** with the app icon, plus a Start Menu entry. Config stays in `%APPDATA%\NiftyAnalyzer`.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1          # in-place + Desktop app shortcut
.\install.ps1 -Launch  # same, then open the desk
```

After that, launch from the Desktop icon (or `Nifty Analyzer.bat` / `.\run.ps1`).

To build a **Setup.exe** you can install like any Windows app (no Python on the target PC): double-click **`Build-Setup.bat`**. Output: `dist\windows\NiftyAnalyzer-Setup-2.0.0.exe`. Needs Inno Setup 6 + Python 3.12 on the **build** PC only.

Uninstall shortcuts + venv (keeps this folder): `.\uninstall.ps1`

## Run from source

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python desktop.py           # starts the local server and opens the desk
```

- `MARKET_DATA_MODE=replay` (default) — deterministic session tape so the desk works without Kite.
- `MARKET_DATA_MODE=live` — read-only Kite (`KITE_API_KEY` + daily token in `%APPDATA%\NiftyAnalyzer\.env`).

Kite Connect **Redirect URL**: `http://127.0.0.1:8000/kite/callback`

## Docker (always-on)

```bash
cd deploy
cp ../assets/.env.default .env   # put Kite keys here; never in a client bundle
docker compose up --build
```

Then `python desktop.py --client --url http://127.0.0.1:8000`. Closing the desktop does **not** stop collection. Re-opening calls `GET /api/session/replay`.

## Tests

```bash
MARKET_DATA_MODE=replay pytest tests -q
```

Safety tests fail the build if `place_order` / `modify_order` / `cancel_order` appear as calls, if the Kite wrapper exposes execution methods, or if a usable order endpoint exists.

## Layout

| Path | Role |
|------|------|
| `backend/` | Intelligence server |
| `backend/safety/` | Hard disable + sealed Kite |
| `backend/kite/` | Read-only wrapper |
| `backend/feed/` | Single market bus + optional KiteTicker |
| `backend/session/` | 08:30–16:30 IST runner + NSE holidays |
| `backend/analytics/` | CVD, OI/flow, PCR, volume/TA, ICT, regime, news |
| `backend/signals/` | Frozen score, engine, lifecycle, paper tracking |
| `backend/agents/` | Specialist analysts + master (no broker tools) |
| `frontend/` | Command Desk UI (fixed viewport, virtualized chain) |
| `desktop.py` | pywebview/browser client |
| `INSTALL.bat` / `install.ps1` | In-place Windows install + Desktop app shortcut |
| `installer/` | Inno Setup script for Setup.exe |
| `deploy/` | Docker Compose + Nginx |

CVD is always labeled **ESTIMATED CVD** (Lee-Ready). Kite does not provide aggressor flags.

Institutional score weights are constants (CVD 20, OI 20, price 20, volume 10, PCR 10, ICT 10, news 5, regime 5). Mixed evidence yields **NO HIGH-CONFIDENCE SIGNAL**. PCR never independently emits a signal.

## AWS Mumbai

Deferred. Compose is the production-shaped stack (4 vCPU / 8–16 GB class). Terraform/HTTPS/S3/CloudWatch when an account, domain, and Kite redirect URL are available.
