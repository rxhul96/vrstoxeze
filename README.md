# Nifty Institutional Command Desk

NIFTY 50 market intelligence (signal-only analyzer) plus a governed NSE options **Trading Desk**: an always-on server and a visualization desktop.

**THE ANALYZER NEVER TRADES.** Automated execution exists only inside the governed Trading Desk — paper by default; live orders require `ALLOW_LIVE_ORDERS=true` *and* a per-order human confirmation, and the human can kill the day at any time.

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

Inside the analyzer there is no path `signal → broker → order`: its Kite client is sealed read-only and is used only for LTP, OHLC, history, instruments, quotes, OI, volume, depth, and WebSocket ticks.

The **Trading Desk** (sidebar → *Trading Desk*, API under `/desk`) is the single, separate, governed path that may place orders. It is the vendored [`optionsdesk`](desk/README.md) package: paper broker by default, `ALLOW_LIVE_ORDERS=false`, NFO options only, max 5 trades / 3 losses a day, arm-for-the-day + kill switch, append-only `risk_events` audit. See [Trading Desk](#trading-desk).

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

## Trading Desk

```
QUANT ENGINES / AI ANALYSTS / SIGNAL ENGINE  (signal-only, sealed Kite)
        ↓  backend/trading_desk/adapter.py   one strategy_id per source, NFO option symbols only
POST /desk/signals → eligibility registry → risk governor → paper broker | Kite (live, confirmed)
        ↓
Trading Desk window: Risk Status (ARM / KILL SWITCH), trade queue, risk_events, strategy registry
```

- **Sources wired** (`DESK_ADAPTER_SOURCES`): `composite_score` (signal engine), `cvd_flow`, `oi_flow`,
  `ict_liquidity`, `price_action_ta`, `ai_master_analyst`. PCR, news and regime are context filters and are
  not wired. Each source fires once per bias *transition* (rate limited by `DESK_ADAPTER_COOLDOWN_SEC`) as a
  BUY of the nearest-expiry ATM NIFTY CE/PE; premium SL/target are delta-scaled from the analyzer's spot levels.
- Every source is registered in the desk's eligibility registry as `NOT_TESTED` and **cannot trade** until
  backtest results are posted (`POST /desk/strategies`) and the desk is armed for the day from the UI.
- One Kite login: the token from `/kite/callback` (or `KITE_ACCESS_TOKEN`) is shared with the desk's broker.
  The analyzer's own client stays sealed read-only.
- Live orders need `ALLOW_LIVE_ORDERS=true` **and** a per-order confirmation phrase in the window.
- The desk panel is the `optionsdesk` React bundle (`desk/ui/dist-lib`), loaded with React from esm.sh inside a
  shadow root; offline, a plain fallback still shows the counters with ARM and KILL SWITCH.

## Tests

```bash
MARKET_DATA_MODE=replay pytest -q          # analyzer suite (tests/) + vendored desk suite (desk/tests)
```

Safety tests fail the build if `place_order` / `modify_order` / `cancel_order` appear as calls anywhere
outside `desk/src/optionsdesk/{engine,brokers/base,brokers/kite}.py`, if the analyzer's Kite wrapper exposes
execution methods, or if a usable order endpoint exists under `/api`.

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
| `backend/trading_desk/` | Desk runtime (paper/live broker, shared Kite login) + signal adapter + Kite symbol builder |
| `desk/` | Vendored `optionsdesk` governor/engine/router/UI (subtree of `vrstoxeze-options-desk-8048`) |
| `frontend/` | Command Desk UI (fixed viewport, virtualized chain) + Trading Desk window (`desk.js`) |
| `desktop.py` | pywebview/browser client |
| `INSTALL.bat` / `install.ps1` | In-place Windows install + Desktop app shortcut |
| `installer/` | Inno Setup script for Setup.exe |
| `deploy/` | Docker Compose + Nginx |

CVD is always labeled **ESTIMATED CVD** (Lee-Ready). Kite does not provide aggressor flags.

Institutional score weights are constants (CVD 20, OI 20, price 20, volume 10, PCR 10, ICT 10, news 5, regime 5). Mixed evidence yields **NO HIGH-CONFIDENCE SIGNAL**. PCR never independently emits a signal.

## AWS Mumbai

Deferred. Compose is the production-shaped stack (4 vCPU / 8–16 GB class). Terraform/HTTPS/S3/CloudWatch when an account, domain, and Kite redirect URL are available.
