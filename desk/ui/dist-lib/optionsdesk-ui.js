var M = Object.defineProperty;
var q = (r, t, l) => t in r ? M(r, t, { enumerable: !0, configurable: !0, writable: !0, value: l }) : r[t] = l;
var b = (r, t, l) => q(r, typeof t != "symbol" ? t + "" : t, l);
import { jsxs as a, jsx as e, Fragment as C } from "react/jsx-runtime";
import { useState as _, useRef as V, useCallback as R, useEffect as j, useMemo as U } from "react";
class B extends Error {
  constructor(t, l) {
    super(l), this.status = t;
  }
}
class G {
  constructor(t = "/desk", l, c = "operator") {
    b(this, "status", () => this.request("/status"));
    b(this, "trades", (t = 200) => this.request(`/trades?limit=${t}`));
    b(this, "riskEvents", (t = 200) => this.request(`/risk-events?limit=${t}`));
    b(this, "signals", (t = 100) => this.request(`/signals?limit=${t}`));
    b(this, "strategies", () => this.request("/strategies"));
    b(this, "arm", () => this.post("/arm", { confirm: !0 }));
    b(this, "disarm", () => this.post("/disarm"));
    b(this, "kill", (t) => this.post("/kill", { reason: t }));
    b(this, "clearStop", (t, l) => this.post("/clear-stop", { phrase: t, note: l }));
    b(this, "confirmTrade", (t, l) => this.post(`/trades/${t}/confirm`, { phrase: l }));
    b(this, "cancelTrade", (t) => this.post(`/trades/${t}/cancel`));
    b(this, "closeTrade", (t) => this.post(`/trades/${t}/close`));
    this.base = t, this.token = l, this.actor = c;
  }
  async request(t, l) {
    const c = { "Content-Type": "application/json" };
    this.token && (c["X-Desk-Token"] = this.token);
    const s = await fetch(`${this.base}${t}`, { ...l, headers: c });
    if (!s.ok) {
      let o = s.statusText;
      try {
        const d = await s.json();
        o = typeof d.detail == "string" ? d.detail : JSON.stringify(d.detail ?? d);
      } catch {
      }
      throw new B(s.status, o);
    }
    return await s.json();
  }
  post(t, l = {}) {
    return this.request(t, { method: "POST", body: JSON.stringify({ actor: this.actor, ...l }) });
  }
}
function w(r, t, l = []) {
  const [c, s] = _(null), [o, d] = _(null), g = V(r);
  g.current = r;
  const m = R(async () => {
    try {
      s(await g.current()), d(null);
    } catch (p) {
      d(p instanceof Error ? p.message : String(p));
    }
  }, []);
  return j(() => {
    let p = !0;
    const x = async () => {
      p && await m();
    };
    x();
    const u = setInterval(x, t);
    return () => {
      p = !1, clearInterval(u);
    };
  }, [t, m, ...l]), { data: c, error: o, refresh: m };
}
function P(r) {
  return r == null ? "—" : `${r > 0 ? "+" : r < 0 ? "−" : ""}₹${Math.abs(r).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}
function A(r) {
  return r ? new Date(r).toLocaleTimeString("en-IN", { hour12: !1, timeZone: "Asia/Kolkata" }) : "—";
}
function k({ title: r, right: t, children: l, className: c = "" }) {
  return /* @__PURE__ */ a("section", { className: `rounded border border-term-border bg-term-panel ${c}`, children: [
    /* @__PURE__ */ a("header", { className: "flex items-center justify-between border-b border-term-border px-3 py-1.5", children: [
      /* @__PURE__ */ e("h2", { className: "text-[11px] font-semibold uppercase tracking-wider text-zinc-400", children: r }),
      t
    ] }),
    /* @__PURE__ */ e("div", { className: "p-3", children: l })
  ] });
}
const I = {
  ACTIVE: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  STOPPED_LOSSES: "bg-red-500/15 text-red-300 border-red-500/40",
  STOPPED_CAP: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  STOPPED_MANUAL: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/40"
};
function v({ children: r, tone: t = "zinc" }) {
  const l = {
    zinc: "border-zinc-600 text-zinc-300",
    green: "border-emerald-500/50 text-emerald-300",
    red: "border-red-500/50 text-red-300",
    amber: "border-amber-500/50 text-amber-300",
    cyan: "border-cyan-500/50 text-cyan-300",
    fuchsia: "border-fuchsia-500/50 text-fuchsia-300"
  };
  return /* @__PURE__ */ e("span", { className: `inline-block rounded border px-1.5 py-px text-[10px] font-semibold tracking-wide ${l[t] ?? l.zinc}`, children: r });
}
function y({
  children: r,
  onClick: t,
  tone: l = "zinc",
  disabled: c,
  title: s,
  className: o = ""
}) {
  return /* @__PURE__ */ e(
    "button",
    {
      type: "button",
      title: s,
      disabled: c,
      onClick: t,
      className: `rounded border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide transition disabled:cursor-not-allowed disabled:opacity-40 ${{
        zinc: "border-zinc-600 bg-zinc-800 hover:bg-zinc-700 text-zinc-100",
        green: "border-emerald-600 bg-emerald-700/80 hover:bg-emerald-600 text-white",
        red: "border-red-600 bg-red-700 hover:bg-red-600 text-white",
        amber: "border-amber-600 bg-amber-700/80 hover:bg-amber-600 text-white"
      }[l]} ${o}`,
      children: r
    }
  );
}
function L({ value: r, max: t, tone: l }) {
  const c = Math.min(100, r / Math.max(1, t) * 100);
  return /* @__PURE__ */ e("div", { className: "h-1.5 w-full overflow-hidden rounded bg-zinc-800", children: /* @__PURE__ */ e("div", { className: `h-full ${l === "red" ? "bg-red-500" : l === "amber" ? "bg-amber-500" : "bg-emerald-500"} transition-all`, style: { width: `${c}%` } }) });
}
function O({ label: r, value: t, sub: l, tone: c = "" }) {
  return /* @__PURE__ */ a("div", { className: "flex flex-col gap-0.5", children: [
    /* @__PURE__ */ e("span", { className: "text-[10px] uppercase tracking-wider text-zinc-500", children: r }),
    /* @__PURE__ */ e("span", { className: `text-lg font-bold leading-none ${c}`, children: t }),
    l && /* @__PURE__ */ e("span", { className: "text-[10px] text-zinc-500", children: l })
  ] });
}
const K = {
  ARMED: "green",
  DISARMED: "amber",
  TRADE_OPENED: "cyan",
  TRADE_CLOSED: "zinc",
  STOPPED_CAP: "amber",
  STOPPED_LOSSES: "red",
  KILL_SWITCH: "red",
  STOP_CLEARED: "fuchsia",
  DAY_RESET: "zinc"
};
function H({ events: r }) {
  return /* @__PURE__ */ e(k, { title: "Risk events (append-only audit)", className: "h-full", children: /* @__PURE__ */ e("div", { className: "max-h-80 overflow-auto", children: /* @__PURE__ */ a("table", { className: "w-full text-left text-[11px]", children: [
    /* @__PURE__ */ e("thead", { className: "text-[10px] uppercase text-zinc-500", children: /* @__PURE__ */ a("tr", { children: [
      /* @__PURE__ */ e("th", { className: "pb-1", children: "#" }),
      /* @__PURE__ */ e("th", { children: "Time" }),
      /* @__PURE__ */ e("th", { children: "Event" }),
      /* @__PURE__ */ e("th", { children: "Status" }),
      /* @__PURE__ */ e("th", { children: "T/L" }),
      /* @__PURE__ */ e("th", { children: "PnL" }),
      /* @__PURE__ */ e("th", { children: "Actor" }),
      /* @__PURE__ */ e("th", { children: "Reason" })
    ] }) }),
    /* @__PURE__ */ a("tbody", { children: [
      (r ?? []).map((t) => /* @__PURE__ */ a("tr", { className: "border-t border-term-border/60 text-zinc-300", children: [
        /* @__PURE__ */ e("td", { className: "py-1 text-zinc-500", children: t.id }),
        /* @__PURE__ */ e("td", { className: "text-zinc-500", children: A(t.created_at) }),
        /* @__PURE__ */ e("td", { children: /* @__PURE__ */ e(v, { tone: K[t.event] ?? "zinc", children: t.event }) }),
        /* @__PURE__ */ e("td", { className: "whitespace-nowrap", children: t.from_status !== t.to_status ? /* @__PURE__ */ a(C, { children: [
          /* @__PURE__ */ e("span", { className: `rounded border px-1 ${I[t.from_status]}`, children: t.from_status }),
          /* @__PURE__ */ e("span", { className: "text-zinc-500", children: " → " }),
          /* @__PURE__ */ e("span", { className: `rounded border px-1 ${I[t.to_status]}`, children: t.to_status })
        ] }) : /* @__PURE__ */ e("span", { className: "text-zinc-500", children: t.to_status }) }),
        /* @__PURE__ */ a("td", { className: "text-zinc-400", children: [
          t.trades_today,
          "/",
          t.losses_today
        ] }),
        /* @__PURE__ */ e("td", { className: t.realized_pnl_today > 0 ? "text-emerald-300" : t.realized_pnl_today < 0 ? "text-red-300" : "text-zinc-400", children: P(t.realized_pnl_today) }),
        /* @__PURE__ */ e("td", { className: "text-zinc-400", children: t.actor }),
        /* @__PURE__ */ a("td", { className: "text-zinc-400", children: [
          t.reason,
          t.trade_id != null && /* @__PURE__ */ a("span", { className: "text-zinc-600", children: [
            " · trade ",
            t.trade_id
          ] })
        ] })
      ] }, t.id)),
      (r ?? []).length === 0 && /* @__PURE__ */ e("tr", { children: /* @__PURE__ */ e("td", { colSpan: 8, className: "py-4 text-center text-zinc-600", children: "no events yet" }) })
    ] })
  ] }) }) });
}
function J({ status: r, api: t, onChanged: l, onError: c }) {
  const [s, o] = _(0), [d, g] = _(0), [m, p] = _(!1), [x, u] = _(""), [f, z] = _("");
  j(() => {
    if (s === 0 && d === 0) return;
    const T = setTimeout(() => {
      o(0), g(0);
    }, 6e3);
    return () => clearTimeout(T);
  }, [s, d]);
  const N = async (T) => {
    p(!0);
    try {
      await T(), c(null), l();
    } catch (D) {
      c(D instanceof Error ? D.message : String(D));
    } finally {
      p(!1), o(0), g(0);
    }
  }, i = r == null ? void 0 : r.risk, h = r == null ? void 0 : r.limits, E = (i == null ? void 0 : i.day_status) ?? "ACTIVE", n = E !== "ACTIVE", S = E === "STOPPED_LOSSES" || E === "STOPPED_MANUAL", F = ((i == null ? void 0 : i.realized_pnl_today) ?? 0) > 0 ? "text-emerald-300" : ((i == null ? void 0 : i.realized_pnl_today) ?? 0) < 0 ? "text-red-300" : "text-zinc-200";
  return /* @__PURE__ */ a(
    k,
    {
      title: "Risk Status",
      right: /* @__PURE__ */ a("div", { className: "flex items-center gap-2", children: [
        r && /* @__PURE__ */ e(v, { tone: r.mode === "live" ? "red" : "cyan", children: r.mode === "live" ? "LIVE ORDERS" : "PAPER" }),
        r && /* @__PURE__ */ a("span", { className: "flex items-center gap-1 text-[10px] text-zinc-400", children: [
          /* @__PURE__ */ e("span", { className: `inline-block h-1.5 w-1.5 rounded-full ${r.market_open ? "bg-emerald-400" : "bg-zinc-600"}` }),
          r.market_open ? "NSE OPEN" : "NSE CLOSED"
        ] })
      ] }),
      children: [
        /* @__PURE__ */ a("div", { className: "flex flex-wrap items-start gap-6", children: [
          /* @__PURE__ */ a("div", { className: "flex min-w-[160px] flex-col gap-2", children: [
            /* @__PURE__ */ e("span", { className: "text-[10px] uppercase tracking-wider text-zinc-500", children: "Day status" }),
            /* @__PURE__ */ e("span", { className: `w-fit rounded border px-2 py-1 text-sm font-bold tracking-wider ${I[E]}`, children: E }),
            /* @__PURE__ */ e("span", { className: "text-[10px] text-zinc-500", children: r != null && r.armed ? /* @__PURE__ */ a("span", { className: "text-emerald-400", children: [
              "ARMED for ",
              i == null ? void 0 : i.armed_for_day
            ] }) : /* @__PURE__ */ e("span", { className: "text-amber-400", children: "NOT ARMED — nothing will trade" }) })
          ] }),
          /* @__PURE__ */ a("div", { className: "grid flex-1 grid-cols-3 gap-6 min-w-[300px]", children: [
            /* @__PURE__ */ a("div", { className: "flex flex-col gap-1.5", children: [
              /* @__PURE__ */ e(
                O,
                {
                  label: "Trades",
                  value: /* @__PURE__ */ a(C, { children: [
                    (i == null ? void 0 : i.trades_today) ?? 0,
                    /* @__PURE__ */ a("span", { className: "text-zinc-500 text-sm", children: [
                      " / ",
                      (h == null ? void 0 : h.max_trades_per_day) ?? 5
                    ] })
                  ] }),
                  sub: `${(h == null ? void 0 : h.base_tier_trades) ?? 3} base · rest sure-shot only`
                }
              ),
              /* @__PURE__ */ e(L, { value: (i == null ? void 0 : i.trades_today) ?? 0, max: (h == null ? void 0 : h.max_trades_per_day) ?? 5, tone: "amber" })
            ] }),
            /* @__PURE__ */ a("div", { className: "flex flex-col gap-1.5", children: [
              /* @__PURE__ */ e(
                O,
                {
                  label: "Losses",
                  value: /* @__PURE__ */ a(C, { children: [
                    (i == null ? void 0 : i.losses_today) ?? 0,
                    /* @__PURE__ */ a("span", { className: "text-zinc-500 text-sm", children: [
                      " / ",
                      (h == null ? void 0 : h.max_losses_per_day) ?? 3
                    ] })
                  ] }),
                  sub: i != null && i.loss_stop_cleared ? "loss stop manually cleared" : "realized losses on closed trades"
                }
              ),
              /* @__PURE__ */ e(L, { value: (i == null ? void 0 : i.losses_today) ?? 0, max: (h == null ? void 0 : h.max_losses_per_day) ?? 3, tone: "red" })
            ] }),
            /* @__PURE__ */ e(
              O,
              {
                label: "Realized PnL",
                value: P(i == null ? void 0 : i.realized_pnl_today),
                tone: F,
                sub: `unrealized ${P(r == null ? void 0 : r.unrealized_pnl)} · ${(r == null ? void 0 : r.open_trades) ?? 0} open · ${(r == null ? void 0 : r.pending_confirmations) ?? 0} pending`
              }
            )
          ] }),
          /* @__PURE__ */ a("div", { className: "flex flex-col items-stretch gap-2 min-w-[190px]", children: [
            r != null && r.armed ? /* @__PURE__ */ e(y, { tone: "zinc", disabled: m, onClick: () => N(t.disarm), children: "Disarm" }) : s === 0 ? /* @__PURE__ */ e(y, { tone: "green", disabled: m || n, title: n ? "clear the stop first" : "arm the desk for today", onClick: () => o(1), children: "Arm for today" }) : /* @__PURE__ */ e(y, { tone: "green", disabled: m, onClick: () => N(t.arm), children: "Confirm arm ✓" }),
            d === 0 ? /* @__PURE__ */ e(y, { tone: "red", disabled: m, className: "py-2 text-xs", onClick: () => g(1), title: "stop day, cancel orders, flatten positions", children: "■ Kill switch" }) : /* @__PURE__ */ e(y, { tone: "red", disabled: m, className: "py-2 text-xs animate-pulse", onClick: () => N(() => t.kill("kill switch (UI)")), children: "Confirm kill — flatten all" })
          ] })
        ] }),
        S && /* @__PURE__ */ a("div", { className: "mt-3 flex flex-wrap items-end gap-2 border-t border-term-border pt-3", children: [
          /* @__PURE__ */ a("div", { className: "flex flex-col gap-1", children: [
            /* @__PURE__ */ a("label", { className: "text-[10px] uppercase tracking-wider text-zinc-500", children: [
              "Type the confirmation phrase to clear ",
              E
            ] }),
            /* @__PURE__ */ e(
              "input",
              {
                value: x,
                onChange: (T) => u(T.target.value),
                placeholder: "I ACCEPT THE RISK",
                className: "w-64 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100 outline-none focus:border-amber-500"
              }
            )
          ] }),
          /* @__PURE__ */ a("div", { className: "flex flex-col gap-1", children: [
            /* @__PURE__ */ e("label", { className: "text-[10px] uppercase tracking-wider text-zinc-500", children: "Note (logged)" }),
            /* @__PURE__ */ e(
              "input",
              {
                value: f,
                onChange: (T) => z(T.target.value),
                placeholder: "why is it safe to resume?",
                className: "w-64 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100 outline-none focus:border-amber-500"
              }
            )
          ] }),
          /* @__PURE__ */ e(
            y,
            {
              tone: "amber",
              disabled: m || !x,
              onClick: () => N(async () => {
                await t.clearStop(x, f), u(""), z("");
              }),
              children: "Clear stop"
            }
          ),
          E === "STOPPED_LOSSES" && /* @__PURE__ */ e("span", { className: "text-[10px] text-zinc-500", children: "Clearing restores ACTIVE for exits/monitoring; new entries stay blocked while losses ≥ limit." })
        ] }),
        E === "STOPPED_CAP" && /* @__PURE__ */ e("p", { className: "mt-3 border-t border-term-border pt-2 text-[10px] text-amber-400", children: "Daily trade cap reached. This stop cannot be cleared; the desk resets at 09:15 IST." })
      ]
    }
  );
}
const W = {
  ELIGIBLE: "green",
  NOT_TESTED: "zinc",
  FAILED: "red",
  STALE: "amber"
};
function Y({ strategies: r }) {
  return /* @__PURE__ */ e(k, { title: "Strategy eligibility", className: "h-full", children: /* @__PURE__ */ a("table", { className: "w-full text-left text-[11px]", children: [
    /* @__PURE__ */ e("thead", { className: "text-[10px] uppercase text-zinc-500", children: /* @__PURE__ */ a("tr", { children: [
      /* @__PURE__ */ e("th", { className: "pb-1", children: "Strategy" }),
      /* @__PURE__ */ e("th", { children: "Status" }),
      /* @__PURE__ */ e("th", { children: "OOS Sharpe" }),
      /* @__PURE__ */ e("th", { children: "Win" }),
      /* @__PURE__ */ e("th", { children: "Trades" }),
      /* @__PURE__ */ e("th", { children: "DD%" }),
      /* @__PURE__ */ e("th", { children: "Hash" }),
      /* @__PURE__ */ e("th", { children: "Why" })
    ] }) }),
    /* @__PURE__ */ a("tbody", { children: [
      (r ?? []).map((t) => {
        var l, c, s;
        return /* @__PURE__ */ a("tr", { className: "border-t border-term-border/60 text-zinc-300", children: [
          /* @__PURE__ */ e("td", { className: "py-1 font-semibold text-zinc-100", children: t.strategy_id }),
          /* @__PURE__ */ e("td", { children: /* @__PURE__ */ e(v, { tone: W[t.status], children: t.status }) }),
          /* @__PURE__ */ e("td", { children: ((l = t.backtest) == null ? void 0 : l.oos_sharpe.toFixed(2)) ?? "—" }),
          /* @__PURE__ */ e("td", { children: t.backtest ? `${(t.backtest.win_rate * 100).toFixed(0)}%` : "—" }),
          /* @__PURE__ */ e("td", { children: ((c = t.backtest) == null ? void 0 : c.trades) ?? "—" }),
          /* @__PURE__ */ e("td", { children: ((s = t.backtest) == null ? void 0 : s.max_drawdown_pct) ?? "—" }),
          /* @__PURE__ */ e("td", { className: "text-zinc-500", children: t.code_hash.slice(0, 10) }),
          /* @__PURE__ */ e("td", { className: "text-zinc-400", children: t.status_reason })
        ] }, t.strategy_id);
      }),
      (r ?? []).length === 0 && /* @__PURE__ */ e("tr", { children: /* @__PURE__ */ e("td", { colSpan: 8, className: "py-4 text-center text-zinc-600", children: "no strategies registered — POST /desk/strategies" }) })
    ] })
  ] }) });
}
function Q({ trades: r, signals: t, api: l, onChanged: c, onError: s }) {
  const [o, d] = _("open"), [g, m] = _(null), [p, x] = _(""), u = r ?? [], f = u.filter((n) => n.status === "PENDING_CONFIRMATION"), z = u.filter((n) => n.status === "OPEN"), N = u.filter((n) => ["CLOSED", "CANCELLED", "EXPIRED", "REJECTED"].includes(n.status)), i = (t ?? []).filter((n) => !n.accepted), h = async (n) => {
    try {
      await n(), s(null), c();
    } catch (S) {
      s(S instanceof Error ? S.message : String(S));
    } finally {
      m(null), x("");
    }
  }, E = [
    { id: "pending", label: "Pending live", n: f.length, tone: f.length ? "red" : void 0 },
    { id: "open", label: "Open", n: z.length },
    { id: "closed", label: "Closed", n: N.length },
    { id: "rejected", label: "Rejected signals", n: i.length }
  ];
  return /* @__PURE__ */ e(
    k,
    {
      title: "Trades",
      right: /* @__PURE__ */ e("nav", { className: "flex gap-1", children: E.map((n) => /* @__PURE__ */ a(
        "button",
        {
          type: "button",
          onClick: () => d(n.id),
          className: `rounded px-2 py-0.5 text-[10px] uppercase tracking-wide ${o === n.id ? "bg-zinc-700 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"}`,
          children: [
            n.label,
            " ",
            /* @__PURE__ */ e("span", { className: n.tone === "red" ? "text-red-400" : "text-zinc-500", children: n.n })
          ]
        },
        n.id
      )) }),
      children: /* @__PURE__ */ e("div", { className: "max-h-72 overflow-auto", children: o === "rejected" ? /* @__PURE__ */ a("table", { className: "w-full text-left text-[11px]", children: [
        /* @__PURE__ */ e("thead", { className: "text-[10px] uppercase text-zinc-500", children: /* @__PURE__ */ a("tr", { children: [
          /* @__PURE__ */ e("th", { className: "pb-1", children: "Time" }),
          /* @__PURE__ */ e("th", { children: "Strategy" }),
          /* @__PURE__ */ e("th", { children: "Symbol" }),
          /* @__PURE__ */ e("th", { children: "Conf" }),
          /* @__PURE__ */ e("th", { children: "Elig" }),
          /* @__PURE__ */ e("th", { children: "Reason" })
        ] }) }),
        /* @__PURE__ */ a("tbody", { children: [
          i.map((n) => /* @__PURE__ */ a("tr", { className: "border-t border-term-border/60 text-zinc-300", children: [
            /* @__PURE__ */ e("td", { className: "py-1 text-zinc-500", children: A(n.received_at) }),
            /* @__PURE__ */ e("td", { children: n.payload.strategy_id }),
            /* @__PURE__ */ e("td", { children: n.payload.tradingsymbol }),
            /* @__PURE__ */ a("td", { children: [
              (n.payload.confidence * 100).toFixed(0),
              "%"
            ] }),
            /* @__PURE__ */ e("td", { children: /* @__PURE__ */ e(v, { tone: n.eligibility === "ELIGIBLE" ? "green" : "amber", children: n.eligibility }) }),
            /* @__PURE__ */ a("td", { className: "text-zinc-400", children: [
              /* @__PURE__ */ e("span", { className: "text-amber-300", children: n.reason_code }),
              " · ",
              n.reason
            ] })
          ] }, n.id)),
          i.length === 0 && /* @__PURE__ */ e($, { text: "no rejected signals" })
        ] })
      ] }) : /* @__PURE__ */ a("table", { className: "w-full text-left text-[11px]", children: [
        /* @__PURE__ */ e("thead", { className: "text-[10px] uppercase text-zinc-500", children: /* @__PURE__ */ a("tr", { children: [
          /* @__PURE__ */ e("th", { className: "pb-1", children: "#" }),
          /* @__PURE__ */ e("th", { children: "Symbol" }),
          /* @__PURE__ */ e("th", { children: "Side" }),
          /* @__PURE__ */ e("th", { children: "Qty" }),
          /* @__PURE__ */ e("th", { children: "Tier" }),
          /* @__PURE__ */ e("th", { children: "Entry" }),
          /* @__PURE__ */ e("th", { children: "SL" }),
          /* @__PURE__ */ e("th", { children: "Target" }),
          /* @__PURE__ */ e("th", { children: "Fill" }),
          /* @__PURE__ */ e("th", { children: "Exit" }),
          /* @__PURE__ */ e("th", { children: "PnL" }),
          /* @__PURE__ */ e("th", { children: "Status" }),
          /* @__PURE__ */ e("th", {})
        ] }) }),
        /* @__PURE__ */ a("tbody", { children: [
          (o === "pending" ? f : o === "open" ? z : N).map((n) => /* @__PURE__ */ a("tr", { className: "border-t border-term-border/60 text-zinc-300", children: [
            /* @__PURE__ */ e("td", { className: "py-1 text-zinc-500", children: n.id }),
            /* @__PURE__ */ e("td", { className: "font-semibold text-zinc-100", children: n.tradingsymbol }),
            /* @__PURE__ */ e("td", { className: n.direction === "BUY" ? "text-emerald-300" : "text-red-300", children: n.direction }),
            /* @__PURE__ */ a("td", { children: [
              n.quantity,
              " ",
              /* @__PURE__ */ a("span", { className: "text-zinc-500", children: [
                "(",
                n.lots,
                "L)"
              ] })
            ] }),
            /* @__PURE__ */ e("td", { children: /* @__PURE__ */ e(v, { tone: n.tier === "SURE_SHOT" ? "cyan" : "zinc", children: n.tier }) }),
            /* @__PURE__ */ e("td", { children: n.entry_price }),
            /* @__PURE__ */ e("td", { className: "text-red-300/80", children: n.stop_loss }),
            /* @__PURE__ */ e("td", { className: "text-emerald-300/80", children: n.target }),
            /* @__PURE__ */ e("td", { children: n.fill_price ?? "—" }),
            /* @__PURE__ */ a("td", { children: [
              n.exit_price ?? "—",
              " ",
              n.exit_reason && /* @__PURE__ */ e("span", { className: "text-zinc-500", children: n.exit_reason })
            ] }),
            /* @__PURE__ */ e("td", { className: (n.realized_pnl ?? 0) > 0 ? "text-emerald-300" : (n.realized_pnl ?? 0) < 0 ? "text-red-300" : "", children: P(n.realized_pnl) }),
            /* @__PURE__ */ a("td", { children: [
              /* @__PURE__ */ e(v, { tone: n.status === "OPEN" ? "green" : n.status === "PENDING_CONFIRMATION" ? "red" : "zinc", children: n.status }),
              n.mode === "live" && /* @__PURE__ */ a(C, { children: [
                " ",
                /* @__PURE__ */ e(v, { tone: "red", children: "LIVE" })
              ] })
            ] }),
            /* @__PURE__ */ a("td", { className: "whitespace-nowrap text-right", children: [
              n.status === "OPEN" && /* @__PURE__ */ e(y, { tone: "zinc", onClick: () => h(() => l.closeTrade(n.id)), children: "Close" }),
              n.status === "PENDING_CONFIRMATION" && (g === n.id ? /* @__PURE__ */ a("span", { className: "inline-flex items-center gap-1", children: [
                /* @__PURE__ */ e(
                  "input",
                  {
                    autoFocus: !0,
                    value: p,
                    onChange: (S) => x(S.target.value),
                    placeholder: "confirmation phrase",
                    className: "w-44 rounded border border-red-700 bg-zinc-900 px-2 py-1 text-xs outline-none"
                  }
                ),
                /* @__PURE__ */ e(y, { tone: "red", disabled: !p, onClick: () => h(() => l.confirmTrade(n.id, p)), children: "Place live" }),
                /* @__PURE__ */ e(y, { tone: "zinc", onClick: () => m(null), children: "✕" })
              ] }) : /* @__PURE__ */ a("span", { className: "inline-flex gap-1", children: [
                /* @__PURE__ */ e(y, { tone: "red", onClick: () => m(n.id), title: `expires ${A(n.confirm_deadline)}`, children: "Confirm live" }),
                /* @__PURE__ */ e(y, { tone: "zinc", onClick: () => h(() => l.cancelTrade(n.id)), children: "Cancel" })
              ] }))
            ] })
          ] }, n.id)),
          (o === "pending" ? f : o === "open" ? z : N).length === 0 && /* @__PURE__ */ e($, { text: `no ${o} trades` })
        ] })
      ] }) })
    }
  );
}
function $({ text: r }) {
  return /* @__PURE__ */ e("tr", { children: /* @__PURE__ */ e("td", { colSpan: 13, className: "py-4 text-center text-zinc-600", children: r }) });
}
function te({ apiBase: r = "/desk", token: t, actor: l = "operator", pollMs: c = 2e3, showStrategies: s = !0, className: o = "" }) {
  const d = U(() => new G(r, t, l), [r, t, l]), [g, m] = _(null), p = w(d.status, c, [d]), x = w(() => d.trades(), c, [d]), u = w(() => d.riskEvents(), c, [d]), f = w(() => d.signals(), c, [d]), z = w(d.strategies, c * 5, [d]), N = R(() => {
    p.refresh(), x.refresh(), u.refresh(), f.refresh(), z.refresh();
  }, [p, x, u, f, z]), i = p.error;
  return /* @__PURE__ */ a("div", { className: `desk-root flex flex-col gap-3 text-zinc-200 ${o}`, children: [
    (g || i) && /* @__PURE__ */ a("div", { className: "flex items-center justify-between rounded border border-red-700 bg-red-950/60 px-3 py-1.5 text-[11px] text-red-200", children: [
      /* @__PURE__ */ e("span", { children: g ?? `desk API unreachable: ${i}` }),
      /* @__PURE__ */ e("button", { type: "button", className: "text-red-300 hover:text-white", onClick: () => m(null), children: "dismiss" })
    ] }),
    /* @__PURE__ */ e(J, { status: p.data, api: d, onChanged: N, onError: m }),
    /* @__PURE__ */ e(Q, { trades: x.data, signals: f.data, api: d, onChanged: N, onError: m }),
    /* @__PURE__ */ a("div", { className: `grid gap-3 ${s ? "lg:grid-cols-2" : ""}`, children: [
      /* @__PURE__ */ e(H, { events: u.data }),
      s && /* @__PURE__ */ e(Y, { strategies: z.data })
    ] })
  ] });
}
export {
  G as DeskApi,
  B as DeskApiError,
  te as DeskPanel
};
