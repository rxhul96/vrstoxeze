export type DayStatus = "ACTIVE" | "STOPPED_LOSSES" | "STOPPED_CAP" | "STOPPED_MANUAL";

export interface RiskState {
  trading_day: string;
  armed_for_day: string | null;
  trades_today: number;
  losses_today: number;
  realized_pnl_today: number;
  day_status: DayStatus;
  loss_stop_cleared: boolean;
}

export interface DeskStatus {
  now: string;
  mode: "paper" | "live";
  broker: string;
  market_open: boolean;
  armed: boolean;
  risk: RiskState;
  limits: { max_trades_per_day: number; max_losses_per_day: number; base_tier_trades: number };
  open_trades: number;
  pending_confirmations: number;
  unrealized_pnl: number;
  config: Record<string, unknown>;
}

export type TradeStatus = "PENDING_CONFIRMATION" | "OPEN" | "CLOSED" | "REJECTED" | "CANCELLED" | "EXPIRED";

export interface Trade {
  id: number;
  signal_id: number;
  strategy_id: string;
  tradingsymbol: string;
  underlying: string;
  direction: "BUY" | "SELL";
  lots: number;
  quantity: number;
  tier: "BASE" | "SURE_SHOT";
  mode: "paper" | "live";
  status: TradeStatus;
  entry_price: number;
  stop_loss: number;
  target: number;
  fill_price: number | null;
  exit_price: number | null;
  exit_reason: string | null;
  realized_pnl: number | null;
  created_at: string;
  opened_at: string | null;
  closed_at: string | null;
  confirm_deadline: string | null;
  note: string | null;
}

export interface RiskEvent {
  id: number;
  created_at: string;
  trading_day: string;
  event: string;
  from_status: DayStatus;
  to_status: DayStatus;
  trades_today: number;
  losses_today: number;
  realized_pnl_today: number;
  actor: string;
  reason: string;
  signal_id: number | null;
  trade_id: number | null;
}

export interface SignalRecord {
  id: number;
  received_at: string;
  accepted: boolean;
  tier: string | null;
  reason_code: string;
  reason: string;
  eligibility: string;
  trade_id: number | null;
  payload: {
    strategy_id: string;
    tradingsymbol: string;
    direction: "BUY" | "SELL";
    entry: number;
    stop_loss: number;
    target: number;
    confidence: number;
  };
}

export interface StrategyRecord {
  strategy_id: string;
  code_hash: string;
  status: "ELIGIBLE" | "NOT_TESTED" | "FAILED" | "STALE";
  status_reason: string;
  tested_at: string | null;
  backtest: { oos_sharpe: number; win_rate: number; trades: number; max_drawdown_pct: number } | null;
}
