import { useState } from "react";
import type { DeskApi } from "../api";
import { fmtMoney, fmtTime } from "../hooks";
import type { SignalRecord, Trade } from "../types";
import { Badge, Button, Panel } from "./ui";

interface Props {
  trades: Trade[] | null;
  signals: SignalRecord[] | null;
  api: DeskApi;
  onChanged: () => void;
  onError: (msg: string | null) => void;
}

type Tab = "pending" | "open" | "closed" | "rejected";

export function TradesQueue({ trades, signals, api, onChanged, onError }: Props) {
  const [tab, setTab] = useState<Tab>("open");
  const [confirming, setConfirming] = useState<number | null>(null);
  const [phrase, setPhrase] = useState("");
  const all = trades ?? [];
  const pending = all.filter((t) => t.status === "PENDING_CONFIRMATION");
  const open = all.filter((t) => t.status === "OPEN");
  const closed = all.filter((t) => ["CLOSED", "CANCELLED", "EXPIRED", "REJECTED"].includes(t.status));
  const rejected = (signals ?? []).filter((s) => !s.accepted);

  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      onError(null);
      onChanged();
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setConfirming(null);
      setPhrase("");
    }
  };

  const tabs: { id: Tab; label: string; n: number; tone?: string }[] = [
    { id: "pending", label: "Pending live", n: pending.length, tone: pending.length ? "red" : undefined },
    { id: "open", label: "Open", n: open.length },
    { id: "closed", label: "Closed", n: closed.length },
    { id: "rejected", label: "Rejected signals", n: rejected.length },
  ];

  return (
    <Panel
      title="Trades"
      right={
        <nav className="flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`rounded px-2 py-0.5 text-[10px] uppercase tracking-wide ${
                tab === t.id ? "bg-zinc-700 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {t.label} <span className={t.tone === "red" ? "text-red-400" : "text-zinc-500"}>{t.n}</span>
            </button>
          ))}
        </nav>
      }
    >
      <div className="max-h-72 overflow-auto">
        {tab === "rejected" ? (
          <table className="w-full text-left text-[11px]">
            <thead className="text-[10px] uppercase text-zinc-500">
              <tr>
                <th className="pb-1">Time</th>
                <th>Strategy</th>
                <th>Symbol</th>
                <th>Conf</th>
                <th>Elig</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {rejected.map((s) => (
                <tr key={s.id} className="border-t border-term-border/60 text-zinc-300">
                  <td className="py-1 text-zinc-500">{fmtTime(s.received_at)}</td>
                  <td>{s.payload.strategy_id}</td>
                  <td>{s.payload.tradingsymbol}</td>
                  <td>{(s.payload.confidence * 100).toFixed(0)}%</td>
                  <td>
                    <Badge tone={s.eligibility === "ELIGIBLE" ? "green" : "amber"}>{s.eligibility}</Badge>
                  </td>
                  <td className="text-zinc-400">
                    <span className="text-amber-300">{s.reason_code}</span> · {s.reason}
                  </td>
                </tr>
              ))}
              {rejected.length === 0 && <Empty text="no rejected signals" />}
            </tbody>
          </table>
        ) : (
          <table className="w-full text-left text-[11px]">
            <thead className="text-[10px] uppercase text-zinc-500">
              <tr>
                <th className="pb-1">#</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Tier</th>
                <th>Entry</th>
                <th>SL</th>
                <th>Target</th>
                <th>Fill</th>
                <th>Exit</th>
                <th>PnL</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(tab === "pending" ? pending : tab === "open" ? open : closed).map((t) => (
                <tr key={t.id} className="border-t border-term-border/60 text-zinc-300">
                  <td className="py-1 text-zinc-500">{t.id}</td>
                  <td className="font-semibold text-zinc-100">{t.tradingsymbol}</td>
                  <td className={t.direction === "BUY" ? "text-emerald-300" : "text-red-300"}>{t.direction}</td>
                  <td>
                    {t.quantity} <span className="text-zinc-500">({t.lots}L)</span>
                  </td>
                  <td>
                    <Badge tone={t.tier === "SURE_SHOT" ? "cyan" : "zinc"}>{t.tier}</Badge>
                  </td>
                  <td>{t.entry_price}</td>
                  <td className="text-red-300/80">{t.stop_loss}</td>
                  <td className="text-emerald-300/80">{t.target}</td>
                  <td>{t.fill_price ?? "—"}</td>
                  <td>
                    {t.exit_price ?? "—"} {t.exit_reason && <span className="text-zinc-500">{t.exit_reason}</span>}
                  </td>
                  <td className={(t.realized_pnl ?? 0) > 0 ? "text-emerald-300" : (t.realized_pnl ?? 0) < 0 ? "text-red-300" : ""}>
                    {fmtMoney(t.realized_pnl)}
                  </td>
                  <td>
                    <Badge tone={t.status === "OPEN" ? "green" : t.status === "PENDING_CONFIRMATION" ? "red" : "zinc"}>{t.status}</Badge>
                    {t.mode === "live" && (
                      <>
                        {" "}
                        <Badge tone="red">LIVE</Badge>
                      </>
                    )}
                  </td>
                  <td className="whitespace-nowrap text-right">
                    {t.status === "OPEN" && (
                      <Button tone="zinc" onClick={() => run(() => api.closeTrade(t.id))}>
                        Close
                      </Button>
                    )}
                    {t.status === "PENDING_CONFIRMATION" &&
                      (confirming === t.id ? (
                        <span className="inline-flex items-center gap-1">
                          <input
                            autoFocus
                            value={phrase}
                            onChange={(e) => setPhrase(e.target.value)}
                            placeholder="confirmation phrase"
                            className="w-44 rounded border border-red-700 bg-zinc-900 px-2 py-1 text-xs outline-none"
                          />
                          <Button tone="red" disabled={!phrase} onClick={() => run(() => api.confirmTrade(t.id, phrase))}>
                            Place live
                          </Button>
                          <Button tone="zinc" onClick={() => setConfirming(null)}>
                            ✕
                          </Button>
                        </span>
                      ) : (
                        <span className="inline-flex gap-1">
                          <Button tone="red" onClick={() => setConfirming(t.id)} title={`expires ${fmtTime(t.confirm_deadline)}`}>
                            Confirm live
                          </Button>
                          <Button tone="zinc" onClick={() => run(() => api.cancelTrade(t.id))}>
                            Cancel
                          </Button>
                        </span>
                      ))}
                  </td>
                </tr>
              ))}
              {(tab === "pending" ? pending : tab === "open" ? open : closed).length === 0 && <Empty text={`no ${tab} trades`} />}
            </tbody>
          </table>
        )}
      </div>
    </Panel>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <tr>
      <td colSpan={13} className="py-4 text-center text-zinc-600">
        {text}
      </td>
    </tr>
  );
}
