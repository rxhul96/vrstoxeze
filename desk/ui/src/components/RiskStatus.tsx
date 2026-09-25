import { useEffect, useState } from "react";
import type { DeskApi } from "../api";
import { fmtMoney } from "../hooks";
import type { DeskStatus } from "../types";
import { Badge, Button, Meter, Panel, STATUS_STYLE, Stat } from "./ui";

interface Props {
  status: DeskStatus | null;
  api: DeskApi;
  onChanged: () => void;
  onError: (msg: string | null) => void;
}

/**
 * Risk Status widget. The ARM control and the KILL SWITCH are always rendered — there is no prop
 * to hide them, by design.
 */
export function RiskStatus({ status, api, onChanged, onError }: Props) {
  const [armStep, setArmStep] = useState<0 | 1>(0);
  const [killStep, setKillStep] = useState<0 | 1>(0);
  const [busy, setBusy] = useState(false);
  const [phrase, setPhrase] = useState("");
  const [note, setNote] = useState("");

  // Two-step confirmations auto-reset so a stale "confirm" button is never left armed.
  useEffect(() => {
    if (armStep === 0 && killStep === 0) return;
    const id = setTimeout(() => {
      setArmStep(0);
      setKillStep(0);
    }, 6000);
    return () => clearTimeout(id);
  }, [armStep, killStep]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      onError(null);
      onChanged();
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      setArmStep(0);
      setKillStep(0);
    }
  };

  const risk = status?.risk;
  const limits = status?.limits;
  const dayStatus = risk?.day_status ?? "ACTIVE";
  const stopped = dayStatus !== "ACTIVE";
  const clearable = dayStatus === "STOPPED_LOSSES" || dayStatus === "STOPPED_MANUAL";
  const pnlTone =
    (risk?.realized_pnl_today ?? 0) > 0 ? "text-emerald-300" : (risk?.realized_pnl_today ?? 0) < 0 ? "text-red-300" : "text-zinc-200";

  return (
    <Panel
      title="Risk Status"
      right={
        <div className="flex items-center gap-2">
          {status && (
            <Badge tone={status.mode === "live" ? "red" : "cyan"}>{status.mode === "live" ? "LIVE ORDERS" : "PAPER"}</Badge>
          )}
          {status && (
            <span className="flex items-center gap-1 text-[10px] text-zinc-400">
              <span className={`inline-block h-1.5 w-1.5 rounded-full ${status.market_open ? "bg-emerald-400" : "bg-zinc-600"}`} />
              {status.market_open ? "NSE OPEN" : "NSE CLOSED"}
            </span>
          )}
        </div>
      }
    >
      <div className="flex flex-wrap items-start gap-6">
        <div className="flex min-w-[160px] flex-col gap-2">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500">Day status</span>
          <span className={`w-fit rounded border px-2 py-1 text-sm font-bold tracking-wider ${STATUS_STYLE[dayStatus]}`}>
            {dayStatus}
          </span>
          <span className="text-[10px] text-zinc-500">
            {status?.armed ? (
              <span className="text-emerald-400">ARMED for {risk?.armed_for_day}</span>
            ) : (
              <span className="text-amber-400">NOT ARMED — nothing will trade</span>
            )}
          </span>
        </div>

        <div className="grid flex-1 grid-cols-3 gap-6 min-w-[300px]">
          <div className="flex flex-col gap-1.5">
            <Stat
              label="Trades"
              value={
                <>
                  {risk?.trades_today ?? 0}
                  <span className="text-zinc-500 text-sm"> / {limits?.max_trades_per_day ?? 5}</span>
                </>
              }
              sub={`${limits?.base_tier_trades ?? 3} base · rest sure-shot only`}
            />
            <Meter value={risk?.trades_today ?? 0} max={limits?.max_trades_per_day ?? 5} tone="amber" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Stat
              label="Losses"
              value={
                <>
                  {risk?.losses_today ?? 0}
                  <span className="text-zinc-500 text-sm"> / {limits?.max_losses_per_day ?? 3}</span>
                </>
              }
              sub={risk?.loss_stop_cleared ? "loss stop manually cleared" : "realized losses on closed trades"}
            />
            <Meter value={risk?.losses_today ?? 0} max={limits?.max_losses_per_day ?? 3} tone="red" />
          </div>
          <Stat
            label="Realized PnL"
            value={fmtMoney(risk?.realized_pnl_today)}
            tone={pnlTone}
            sub={`unrealized ${fmtMoney(status?.unrealized_pnl)} · ${status?.open_trades ?? 0} open · ${status?.pending_confirmations ?? 0} pending`}
          />
        </div>

        <div className="flex flex-col items-stretch gap-2 min-w-[190px]">
          {status?.armed ? (
            <Button tone="zinc" disabled={busy} onClick={() => run(api.disarm)}>
              Disarm
            </Button>
          ) : armStep === 0 ? (
            <Button tone="green" disabled={busy || stopped} title={stopped ? "clear the stop first" : "arm the desk for today"} onClick={() => setArmStep(1)}>
              Arm for today
            </Button>
          ) : (
            <Button tone="green" disabled={busy} onClick={() => run(api.arm)}>
              Confirm arm ✓
            </Button>
          )}

          {killStep === 0 ? (
            <Button tone="red" disabled={busy} className="py-2 text-xs" onClick={() => setKillStep(1)} title="stop day, cancel orders, flatten positions">
              ■ Kill switch
            </Button>
          ) : (
            <Button tone="red" disabled={busy} className="py-2 text-xs animate-pulse" onClick={() => run(() => api.kill("kill switch (UI)"))}>
              Confirm kill — flatten all
            </Button>
          )}
        </div>
      </div>

      {clearable && (
        <div className="mt-3 flex flex-wrap items-end gap-2 border-t border-term-border pt-3">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-zinc-500">
              Type the confirmation phrase to clear {dayStatus}
            </label>
            <input
              value={phrase}
              onChange={(e) => setPhrase(e.target.value)}
              placeholder="I ACCEPT THE RISK"
              className="w-64 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100 outline-none focus:border-amber-500"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-zinc-500">Note (logged)</label>
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="why is it safe to resume?"
              className="w-64 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100 outline-none focus:border-amber-500"
            />
          </div>
          <Button
            tone="amber"
            disabled={busy || !phrase}
            onClick={() =>
              run(async () => {
                await api.clearStop(phrase, note);
                setPhrase("");
                setNote("");
              })
            }
          >
            Clear stop
          </Button>
          {dayStatus === "STOPPED_LOSSES" && (
            <span className="text-[10px] text-zinc-500">
              Clearing restores ACTIVE for exits/monitoring; new entries stay blocked while losses ≥ limit.
            </span>
          )}
        </div>
      )}
      {dayStatus === "STOPPED_CAP" && (
        <p className="mt-3 border-t border-term-border pt-2 text-[10px] text-amber-400">
          Daily trade cap reached. This stop cannot be cleared; the desk resets at 09:15 IST.
        </p>
      )}
    </Panel>
  );
}
