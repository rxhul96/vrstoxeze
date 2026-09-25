import { fmtMoney, fmtTime } from "../hooks";
import type { RiskEvent } from "../types";
import { Badge, Panel, STATUS_STYLE } from "./ui";

const EVENT_TONE: Record<string, string> = {
  ARMED: "green",
  DISARMED: "amber",
  TRADE_OPENED: "cyan",
  TRADE_CLOSED: "zinc",
  STOPPED_CAP: "amber",
  STOPPED_LOSSES: "red",
  KILL_SWITCH: "red",
  STOP_CLEARED: "fuchsia",
  DAY_RESET: "zinc",
};

export function RiskEventsLog({ events }: { events: RiskEvent[] | null }) {
  return (
    <Panel title="Risk events (append-only audit)" className="h-full">
      <div className="max-h-80 overflow-auto">
        <table className="w-full text-left text-[11px]">
          <thead className="text-[10px] uppercase text-zinc-500">
            <tr>
              <th className="pb-1">#</th>
              <th>Time</th>
              <th>Event</th>
              <th>Status</th>
              <th>T/L</th>
              <th>PnL</th>
              <th>Actor</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {(events ?? []).map((e) => (
              <tr key={e.id} className="border-t border-term-border/60 text-zinc-300">
                <td className="py-1 text-zinc-500">{e.id}</td>
                <td className="text-zinc-500">{fmtTime(e.created_at)}</td>
                <td>
                  <Badge tone={EVENT_TONE[e.event] ?? "zinc"}>{e.event}</Badge>
                </td>
                <td className="whitespace-nowrap">
                  {e.from_status !== e.to_status ? (
                    <>
                      <span className={`rounded border px-1 ${STATUS_STYLE[e.from_status]}`}>{e.from_status}</span>
                      <span className="text-zinc-500"> → </span>
                      <span className={`rounded border px-1 ${STATUS_STYLE[e.to_status]}`}>{e.to_status}</span>
                    </>
                  ) : (
                    <span className="text-zinc-500">{e.to_status}</span>
                  )}
                </td>
                <td className="text-zinc-400">
                  {e.trades_today}/{e.losses_today}
                </td>
                <td className={e.realized_pnl_today > 0 ? "text-emerald-300" : e.realized_pnl_today < 0 ? "text-red-300" : "text-zinc-400"}>
                  {fmtMoney(e.realized_pnl_today)}
                </td>
                <td className="text-zinc-400">{e.actor}</td>
                <td className="text-zinc-400">
                  {e.reason}
                  {e.trade_id != null && <span className="text-zinc-600"> · trade {e.trade_id}</span>}
                </td>
              </tr>
            ))}
            {(events ?? []).length === 0 && (
              <tr>
                <td colSpan={8} className="py-4 text-center text-zinc-600">
                  no events yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
