import { useCallback, useMemo, useState } from "react";
import { DeskApi } from "./api";
import { RiskEventsLog } from "./components/RiskEventsLog";
import { RiskStatus } from "./components/RiskStatus";
import { StrategiesTable } from "./components/StrategiesTable";
import { TradesQueue } from "./components/TradesQueue";
import { usePoll } from "./hooks";

export interface DeskPanelProps {
  /** Base URL of the mounted router, e.g. "/desk" or "http://localhost:8000/desk". */
  apiBase?: string;
  /** Value for the X-Desk-Token header when DESK_API_TOKEN is configured. */
  token?: string;
  /** Actor name written to the audit log for manual actions. */
  actor?: string;
  /** Poll interval in ms. */
  pollMs?: number;
  /** Hide the strategy table (the risk widget and kill switch can never be hidden). */
  showStrategies?: boolean;
  className?: string;
}

export function DeskPanel({ apiBase = "/desk", token, actor = "operator", pollMs = 2000, showStrategies = true, className = "" }: DeskPanelProps) {
  const api = useMemo(() => new DeskApi(apiBase, token, actor), [apiBase, token, actor]);
  const [error, setError] = useState<string | null>(null);

  const status = usePoll(api.status, pollMs, [api]);
  const trades = usePoll(() => api.trades(), pollMs, [api]);
  const events = usePoll(() => api.riskEvents(), pollMs, [api]);
  const signals = usePoll(() => api.signals(), pollMs, [api]);
  const strategies = usePoll(api.strategies, pollMs * 5, [api]);

  const refreshAll = useCallback(() => {
    void status.refresh();
    void trades.refresh();
    void events.refresh();
    void signals.refresh();
    void strategies.refresh();
  }, [status, trades, events, signals, strategies]);

  const connError = status.error;

  return (
    <div className={`desk-root flex flex-col gap-3 text-zinc-200 ${className}`}>
      {(error || connError) && (
        <div className="flex items-center justify-between rounded border border-red-700 bg-red-950/60 px-3 py-1.5 text-[11px] text-red-200">
          <span>{error ?? `desk API unreachable: ${connError}`}</span>
          <button type="button" className="text-red-300 hover:text-white" onClick={() => setError(null)}>
            dismiss
          </button>
        </div>
      )}
      <RiskStatus status={status.data} api={api} onChanged={refreshAll} onError={setError} />
      <TradesQueue trades={trades.data} signals={signals.data} api={api} onChanged={refreshAll} onError={setError} />
      <div className={`grid gap-3 ${showStrategies ? "lg:grid-cols-2" : ""}`}>
        <RiskEventsLog events={events.data} />
        {showStrategies && <StrategiesTable strategies={strategies.data} />}
      </div>
    </div>
  );
}
