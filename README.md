# Nifty Institutional Command Desk

Signal-only NIFTY 50 market intelligence: an always-on server plus a visualization desktop.

**THE HUMAN ALWAYS MAKES THE FINAL TRADING DECISION. NEVER AUTOMATICALLY TRADE.**

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

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export MARKET_DATA_MODE=replay   # live tape without Kite credentials (demo/tests)
export DATABASE_URL=sqlite:///data/nifty_desk.sqlite
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000

- `MARKET_DATA_MODE=live` — read-only Kite (requires `KITE_API_KEY` + daily `KITE_ACCESS_TOKEN` on the **server**).
- `MARKET_DATA_MODE=replay` — deterministic session tape for development. Production should be `live`.

### Desktop (visualization only)

```bash
# Server already running (Docker or uvicorn):
python desktop.py --client --url http://127.0.0.1:8000

# Laptop-only day (embeds uvicorn on this PC):
python desktop.py --serve
```

Closing the desktop does **not** stop a Docker/server process. Re-opening calls `GET /api/session/replay` and reconstructs the session from 09:15.

## Docker (always-on)

```bash
cd deploy
cp ../.env.example .env   # put Kite keys here; never in the desktop
docker compose up --build
```

- API/UI: http://127.0.0.1:8000
- Postgres `nifty_desk` is bound to **localhost only** (`127.0.0.1:5432`)
- Redis is internal
- Nginx on port 80 proxies HTTP + WebSocket

Zerodha access tokens expire every day. At 08:40 the server checks auth; if missing, the status bar shows **KITE LOGIN REQUIRED** and **SIGNALS PAUSED**. Log in via `{ANALYZER_URL}/kite/login` so the callback stores the token on the server volume — the desktop never receives API secrets.

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
| `deploy/` | Docker Compose + Nginx |

CVD is always labeled **ESTIMATED CVD** (Lee-Ready). Kite does not provide aggressor flags.

Institutional score weights are constants (CVD 20, OI 20, price 20, volume 10, PCR 10, ICT 10, news 5, regime 5). Mixed evidence yields **NO HIGH-CONFIDENCE SIGNAL**. PCR never independently emits a signal.

## AWS Mumbai

Deferred. Compose is the production-shaped stack (4 vCPU / 8–16 GB class). Terraform/HTTPS/S3/CloudWatch when an account, domain, and Kite redirect URL are available.
