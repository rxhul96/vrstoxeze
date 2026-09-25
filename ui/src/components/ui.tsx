import type { ReactNode } from "react";
import type { DayStatus } from "../types";

export function Panel({ title, right, children, className = "" }: {
  title: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded border border-term-border bg-term-panel ${className}`}>
      <header className="flex items-center justify-between border-b border-term-border px-3 py-1.5">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">{title}</h2>
        {right}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

export const STATUS_STYLE: Record<DayStatus, string> = {
  ACTIVE: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  STOPPED_LOSSES: "bg-red-500/15 text-red-300 border-red-500/40",
  STOPPED_CAP: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  STOPPED_MANUAL: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/40",
};

export function Badge({ children, tone = "zinc" }: { children: ReactNode; tone?: string }) {
  const tones: Record<string, string> = {
    zinc: "border-zinc-600 text-zinc-300",
    green: "border-emerald-500/50 text-emerald-300",
    red: "border-red-500/50 text-red-300",
    amber: "border-amber-500/50 text-amber-300",
    cyan: "border-cyan-500/50 text-cyan-300",
    fuchsia: "border-fuchsia-500/50 text-fuchsia-300",
  };
  return (
    <span className={`inline-block rounded border px-1.5 py-px text-[10px] font-semibold tracking-wide ${tones[tone] ?? tones.zinc}`}>
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  tone = "zinc",
  disabled,
  title,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  tone?: "zinc" | "green" | "red" | "amber";
  disabled?: boolean;
  title?: string;
  className?: string;
}) {
  const tones = {
    zinc: "border-zinc-600 bg-zinc-800 hover:bg-zinc-700 text-zinc-100",
    green: "border-emerald-600 bg-emerald-700/80 hover:bg-emerald-600 text-white",
    red: "border-red-600 bg-red-700 hover:bg-red-600 text-white",
    amber: "border-amber-600 bg-amber-700/80 hover:bg-amber-600 text-white",
  };
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={`rounded border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide transition disabled:cursor-not-allowed disabled:opacity-40 ${tones[tone]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Meter({ value, max, tone }: { value: number; max: number; tone: "green" | "red" | "amber" }) {
  const pct = Math.min(100, (value / Math.max(1, max)) * 100);
  const color = tone === "red" ? "bg-red-500" : tone === "amber" ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="h-1.5 w-full overflow-hidden rounded bg-zinc-800">
      <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Stat({ label, value, sub, tone = "" }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</span>
      <span className={`text-lg font-bold leading-none ${tone}`}>{value}</span>
      {sub && <span className="text-[10px] text-zinc-500">{sub}</span>}
    </div>
  );
}
