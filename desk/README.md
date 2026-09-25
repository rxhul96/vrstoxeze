# optionsdesk — governed NSE options auto-trading desk

A self-contained Python package (+ embeddable React panel) that turns analyzer signals into
**NSE option** trades under a hard risk governor. Built to be mounted into an existing
FastAPI app (the Nifty Analyzer) as a router; runs standalone for development.

**Defaults are safe:** paper trading, long options only, NFO only, nothing trades until the
desk is armed for the day from the UI.

## Hard rules (enforced in code, covered by tests)

| # | Rule | Where |
|---|------|-------|
| — | Only NFO options (index: NIFTY/BANKNIFTY/FINNIFTY/MIDCPNIFTY; stock options). Any other exchange or instrument is rejected before it reaches a broker. | `instruments.py`, `brokers/base.py` |
| — | Paper by default. Live orders need `ALLOW_LIVE_ORDERS=true` **and** a per-order confirmation phrase in the UI (`POST /desk/trades/{id}/confirm`). | `engine.py` |
| 1 | `trades_today >= 5` → `STOPPED_CAP`. Never clearable. | `risk_governor.py` |
| 2 | `losses_today >= 3` → `STOPPED_LOSSES`. Never auto-resumes; manual clear needs the confirmation phrase and is logged. | `risk_governor.py` |
| 3 | Trades 1–3 execute automatically once the desk is armed and the strategy is `ELIGIBLE`. | `risk_governor.py`, `eligibility.py` |
| 4 | Trades 4–5 only if `realized_pnl_today > 0` and `losses_today < 3` and the signal is a **sure-shot** (defaults: live win-rate ≥ 70 % over ≥ 20 trades, OOS Sharpe ≥ 1.5, confidence in the top decile — all configurable). | `risk_governor.py` |
| 5 | Kill switch: stop the day, cancel open orders, flatten positions. Always visible in the UI. | `engine.kill`, `RiskStatus.tsx` |
| 6 | Every state transition is an immutable row in `risk_events` (sqlite triggers block UPDATE/DELETE). | `store.py` |

Daily state (`trades_today`, `losses_today`, `realized_pnl_today`, `day_status`, `armed_for_day`)
is persisted to SQLite and survives restarts. Counters reset at **09:15 IST**; arming is per
calendar day. A "loss" is a closed trade with negative realized PnL. Default size is 1 lot.

## Quick start (paper)

```bash
make install          # venv + pip install -e ".[dev]" + npm install
make dev              # API on :8000, Vite UI on :5173 (proxies /desk to the API)
```

Or with Docker: `docker compose up --build` → UI + API on <http://localhost:8000>.

Then, in another shell:

```bash
# 1) register a strategy so it becomes ELIGIBLE
curl -sX POST localhost:8000/desk/strategies -H 'content-type: application/json' -d '{
  "strategy_id": "cvd_breakout", "code_hash": "abc123",
  "backtest": {"oos_sharpe": 1.8, "win_rate": 0.62, "trades": 120, "max_drawdown_pct": 8},
  "tested_at": "2026-09-20T10:00:00+05:30"}'

# 2) arm the desk from the UI (or): 
curl -sX POST localhost:8000/desk/arm -H 'content-type: application/json' -d '{"confirm": true, "actor": "rahul"}'

# 3) feed a signal
curl -sX POST localhost:8000/desk/signals -H 'content-type: application/json' -d '{
  "strategy_id": "cvd_breakout", "code_hash": "abc123",
  "tradingsymbol": "NIFTY24SEP25000CE", "exchange": "NFO", "direction": "BUY",
  "entry": 100, "stop_loss": 90, "target": 120, "confidence": 0.82,
  "stats": {"live_win_rate": 0.74, "live_trades": 31, "oos_sharpe": 1.7}}'

# 4) push LTPs (the host app already has the Kite ticker) — SL/target exits fire from these
curl -sX POST localhost:8000/desk/prices -H 'content-type: application/json' -d '{"prices": {"NIFTY24SEP25000CE": 121}}'
```

Set `DESK_MARKET_HOURS_ONLY=false` in `.env` to paper-test outside 09:15–15:30 IST.

## Mounting into the existing FastAPI app

```python
# nifty_analyzer/main.py
from fastapi import FastAPI
from optionsdesk import DeskConfig, build_desk_router
from optionsdesk.engine import build_engine

app = FastAPI()
desk = build_engine(DeskConfig())           # reads ALLOW_LIVE_ORDERS, KITE_*, DESK_* from env/.env
app.include_router(build_desk_router(desk)) # everything under /desk
app.state.desk = desk
```

Feed it from your pipeline without HTTP:

```python
from optionsdesk.models import SignalIn, StrategyStats

rec = app.state.desk.submit_signal(SignalIn(
    strategy_id="cvd_breakout", code_hash=CVD_CODE_HASH,
    tradingsymbol="NIFTY24SEP25000CE", direction="BUY",
    entry=100, stop_loss=90, target=120, confidence=0.82,
    stats=StrategyStats(live_win_rate=0.74, live_trades=31, oos_sharpe=1.7),
))
# rec.accepted, rec.tier ("BASE" | "SURE_SHOT"), rec.reason_code, rec.trade_id

# from your Kite ticker callback:
app.state.desk.on_prices({tick["tradingsymbol"]: tick["last_price"] for tick in ticks})
```

If you already hold a `KiteConnect` instance, pass it in instead of new credentials:

```python
from optionsdesk.brokers.kite import KiteBroker
from optionsdesk.engine import DeskEngine
from optionsdesk.store import DeskStore

cfg = DeskConfig()
broker = KiteBroker(cfg.kite_api_key, cfg.kite_access_token, client=existing_kite)  # only if ALLOW_LIVE_ORDERS
desk = DeskEngine(cfg, DeskStore(cfg.db_path), broker)
```

`DeskEngine` refuses a live broker unless `ALLOW_LIVE_ORDERS=true`.

### API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/desk/status` | risk state, mode, limits, open/pending counts |
| POST | `/desk/arm` `{confirm: true, actor}` | arm for today (fails if the day is stopped) |
| POST | `/desk/disarm` | |
| POST | `/desk/kill` `{reason, actor}` | kill switch |
| POST | `/desk/clear-stop` `{phrase, note, actor}` | clear `STOPPED_LOSSES` / `STOPPED_MANUAL` (never `STOPPED_CAP`) |
| POST | `/desk/signals` | signal intake (422 for non-NFO-option / bad levels; 200 with `accepted=false` for governor blocks) |
| GET | `/desk/signals` | recent signals with reason codes |
| GET | `/desk/trades?status=OPEN` | trade queue |
| POST | `/desk/trades/{id}/confirm` `{phrase}` | live-mode per-order confirmation |
| POST | `/desk/trades/{id}/cancel` | cancel a pending live order |
| POST | `/desk/trades/{id}/close` `{price?}` | manual exit |
| POST | `/desk/prices` `{prices: {sym: ltp}}` | LTP feed → SL/target exits, paper marks |
| GET | `/desk/positions` | broker positions (NFO only) |
| GET | `/desk/risk-events` | append-only audit log |
| GET/POST | `/desk/strategies` | eligibility registry |

Set `DESK_API_TOKEN` to require an `X-Desk-Token` header on every route.

## Embedding the UI

The panel is React 19 + Tailwind v4, dark terminal style. Two options:

1. **Source import** (recommended for the React host): copy or path-alias `ui/src` and render
   `<DeskPanel apiBase="/desk" token={token} actor="rahul" />`. If the host already runs Tailwind v4,
   add `@source "../path/to/ui/src";` to its CSS so the classes are generated; otherwise import
   `ui/src/index.css`.
2. **Prebuilt library:** `cd ui && npm run build:lib` → `ui/dist-lib/optionsdesk-ui.{js,css}`
   (React is external). Import both and render `DeskPanel`.

The Risk Status widget (trade/loss counters, PnL, `day_status`, arm button, kill switch) has no
prop to hide it; `showStrategies={false}` only hides the eligibility table.

Standalone: `cd ui && npm run build` writes into `src/optionsdesk/static`, which
`uvicorn --factory optionsdesk.app:create_app` serves at `/`. Query params `?api=…&token=…&actor=…`
override the defaults.

## Going live (deliberately friction-heavy)

1. `ALLOW_LIVE_ORDERS=true`, `KITE_API_KEY`, `KITE_ACCESS_TOKEN` in `.env`.
2. Arm the desk for the day.
3. Each governor-approved signal appears under **Pending live**; type the confirmation phrase
   within `DESK_LIVE_CONFIRM_TTL_SEC` (default 120 s) or it expires. The governor is re-evaluated
   at confirmation time. Nothing is counted against the daily limits until the order is placed.
4. Exits (SL/target/kill) are MARKET orders on NFO. In live mode the standalone app also polls
   Kite LTPs every `DESK_POLL_SEC` (3 s) for open trades; a host app should call `on_prices` from
   its ticker instead.

## Layout

```
src/optionsdesk/
  risk_governor.py   pure rules 1–6 over an immutable RiskState (no I/O)
  engine.py          DeskEngine: signal → instrument check → eligibility → governor → broker
  eligibility.py     ELIGIBLE | NOT_TESTED | FAILED | STALE (code hash / age / thresholds)
  instruments.py     NFO option tradingsymbol parser; the only gate to a broker
  brokers/           base.py (interface), paper.py, kite.py (kiteconnect)
  store.py           sqlite3: risk_state, risk_events (append-only), signals, trades, strategies
  api.py             FastAPI router      app.py  standalone factory
  config.py          every threshold as a DESK_* env var
ui/                  React + Vite + Tailwind panel (DeskPanel)
tests/               102 tests: governor rules + interactions, engine, brokers, API, store
```

## Development

```bash
make test      # pytest
make lint      # ruff + tsc
make fmt
```
