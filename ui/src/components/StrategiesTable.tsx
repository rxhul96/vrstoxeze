import type { StrategyRecord } from "../types";
import { Badge, Panel } from "./ui";

const TONE: Record<StrategyRecord["status"], string> = {
  ELIGIBLE: "green",
  NOT_TESTED: "zinc",
  FAILED: "red",
  STALE: "amber",
};

export function StrategiesTable({ strategies }: { strategies: StrategyRecord[] | null }) {
  return (
    <Panel title="Strategy eligibility" className="h-full">
      <table className="w-full text-left text-[11px] [&_td]:px-1 [&_th]:px-1">
        <thead className="text-[10px] uppercase text-zinc-500">
          <tr>
            <th className="pb-1">Strategy</th>
            <th>Status</th>
            <th>OOS Sharpe</th>
            <th>Win</th>
            <th>Trades</th>
            <th>DD%</th>
            <th>Hash</th>
            <th>Why</th>
          </tr>
        </thead>
        <tbody>
          {(strategies ?? []).map((s) => (
            <tr key={s.strategy_id} className="border-t border-term-border/60 text-zinc-300">
              <td className="py-1 font-semibold text-zinc-100">{s.strategy_id}</td>
              <td>
                <Badge tone={TONE[s.status]}>{s.status}</Badge>
              </td>
              <td>{s.backtest?.oos_sharpe.toFixed(2) ?? "—"}</td>
              <td>{s.backtest ? `${(s.backtest.win_rate * 100).toFixed(0)}%` : "—"}</td>
              <td>{s.backtest?.trades ?? "—"}</td>
              <td>{s.backtest?.max_drawdown_pct ?? "—"}</td>
              <td className="text-zinc-500" title={s.code_hash}>
                {s.code_hash.slice(0, 8)}
              </td>
              <td className="text-zinc-400">{s.status_reason}</td>
            </tr>
          ))}
          {(strategies ?? []).length === 0 && (
            <tr>
              <td colSpan={8} className="py-4 text-center text-zinc-600">
                no strategies registered — POST /desk/strategies
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </Panel>
  );
}
