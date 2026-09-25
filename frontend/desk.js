// Trading Desk window. Mounts the desk's own React panel (desk/ui/dist-lib, served at /static/desk)
// inside a shadow root so its Tailwind preflight cannot restyle the analyzer, and retunes its
// palette to the analyzer's terminal theme. If React cannot be loaded (offline), a plain fallback
// still shows the risk counters with ARM and KILL SWITCH so the operator is never without controls.
const API = "/desk";
const host = document.getElementById("desk-panel-host");
const modePill = document.getElementById("desk-mode-pill");
const navTag = document.getElementById("nav-desk-mode");
const footer = document.getElementById("st-desk");

// Analyzer palette mapped onto the panel's Tailwind design tokens (all colours are CSS variables in the bundle).
const THEME = `
  :host { display: block; }
  :host, .desk-root {
    --font-mono: "Segoe UI", "IBM Plex Sans", system-ui, sans-serif;
    --color-term-bg: #0b0e11; --color-term-panel: #12161c; --color-term-border: #2a3340;
    --color-zinc-100: #d7dee8; --color-zinc-200: #d7dee8; --color-zinc-300: #c3ccd8; --color-zinc-400: #9aa6b5;
    --color-zinc-500: #7b8796; --color-zinc-600: #55606e; --color-zinc-700: #2a3340; --color-zinc-800: #181d25;
    --color-zinc-900: #12161c; --color-zinc-950: #0b0e11;
    --color-emerald-300: #7fe0b3; --color-emerald-400: #3dcc8a; --color-emerald-500: #3dcc8a;
    --color-emerald-600: #2fa771; --color-emerald-700: #23805a;
    --color-red-200: #f6b3b8; --color-red-300: #f3969c; --color-red-400: #ee6b73; --color-red-500: #ee6b73;
    --color-red-600: #d4525b; --color-red-700: #a83f47; --color-red-950: #2a1214;
    --color-amber-300: #e8c25a; --color-amber-400: #d4a017; --color-amber-500: #d4a017;
    --color-amber-600: #b3870f; --color-amber-700: #8c6a0c;
    --color-cyan-300: #6fd8cf; --color-cyan-400: #2ec4b6; --color-cyan-500: #2ec4b6;
    --color-fuchsia-300: #c7a0ff; --color-fuchsia-500: #4f8cff;
  }
  /* @property rules are ignored inside shadow trees; provide the bundle's defaults explicitly. */
  *, ::before, ::after { --tw-border-style: solid; --tw-leading: initial; --tw-font-weight: initial; --tw-tracking: initial; }
  .desk-root { font-size: 12px; font-variant-numeric: tabular-nums; color: #d7dee8; padding-bottom: 8px; }
`;

function setMode(status) {
  const mode = status ? (status.mode === "live" ? "LIVE ORDERS" : "PAPER") : "OFFLINE";
  const armed = status?.armed ? "ARMED" : "DISARMED";
  const day = status?.risk?.day_status || "";
  modePill.textContent = `${mode} · ${armed}${day && day !== "ACTIVE" ? " · " + day : ""}`;
  modePill.className = "desk-mode-pill " + (status ? (status.mode === "live" ? "live" : "paper") : "off");
  navTag.textContent = status ? (status.mode === "live" ? "LIVE" : "PAPER") : "—";
  footer.textContent = status
    ? `Desk ${mode.toLowerCase()} · ${armed.toLowerCase()} · ${status.risk?.trades_today ?? 0}/${status.limits?.max_trades_per_day ?? 5} trades · ${status.risk?.losses_today ?? 0}/${status.limits?.max_losses_per_day ?? 3} losses`
    : "Desk unreachable";
  footer.className = status ? (status.mode === "live" ? "warn" : "ok") : "bad";
}

async function fetchStatus() {
  try {
    const r = await fetch(`${API}/status`);
    if (!r.ok) throw new Error(r.statusText);
    const s = await r.json();
    setMode(s);
    return s;
  } catch {
    setMode(null);
    return null;
  }
}

async function post(path, body) {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: "operator", ...body }),
  });
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return r.json();
}

// Plain fallback: risk counters + ARM + KILL SWITCH, no framework required.
function mountFallback(reason) {
  host.innerHTML = `
    <div class="desk-fallback">
      <div class="desk-fb-note">Desk panel bundle could not be loaded (${reason}). Minimal controls are active; the kill switch always works.</div>
      <div class="oc-summary" id="desk-fb-boxes"></div>
      <div class="desk-fb-actions">
        <button type="button" id="desk-fb-arm">Arm for today</button>
        <button type="button" id="desk-fb-disarm">Disarm</button>
        <button type="button" id="desk-fb-kill" class="kill">■ KILL SWITCH</button>
        <span id="desk-fb-msg" class="desk-fb-msg"></span>
      </div>
      <div class="win-head" style="margin-top:10px">Trades</div>
      <pre id="desk-fb-trades" class="mono"></pre>
      <div class="win-head">Risk events</div>
      <pre id="desk-fb-events" class="mono"></pre>
    </div>`;
  const msg = document.getElementById("desk-fb-msg");
  const run = (fn) => async () => {
    msg.textContent = "…";
    try { await fn(); msg.textContent = "ok"; } catch (e) { msg.textContent = String(e.message || e); }
    refresh();
  };
  document.getElementById("desk-fb-arm").onclick = run(() => post("/arm", { confirm: true }));
  document.getElementById("desk-fb-disarm").onclick = run(() => post("/disarm", {}));
  document.getElementById("desk-fb-kill").onclick = run(() => {
    if (!window.confirm("KILL SWITCH: stop the day, cancel open orders and flatten all NFO positions?")) return Promise.resolve();
    return post("/kill", { reason: "kill switch (fallback UI)" });
  });
  async function refresh() {
    const s = await fetchStatus();
    const boxes = document.getElementById("desk-fb-boxes");
    if (!boxes) return;
    const r = s?.risk || {};
    const items = [
      ["Mode", s ? s.mode : "offline"], ["Day status", r.day_status ?? "—"], ["Armed", s?.armed ? "yes" : "no"],
      ["Trades", `${r.trades_today ?? 0} / ${s?.limits?.max_trades_per_day ?? 5}`],
      ["Losses", `${r.losses_today ?? 0} / ${s?.limits?.max_losses_per_day ?? 3}`],
      ["Realized PnL", r.realized_pnl_today ?? "—"], ["Open", s?.open_trades ?? 0], ["Pending", s?.pending_confirmations ?? 0],
    ];
    boxes.innerHTML = items.map(([k, v]) => `<div class="oc-sum-box"><span>${k}</span><b>${v}</b></div>`).join("");
    try {
      const trades = await (await fetch(`${API}/trades?limit=25`)).json();
      document.getElementById("desk-fb-trades").textContent = trades.length
        ? trades.map((t) => `#${t.id} ${t.status.padEnd(20)} ${t.strategy_id.padEnd(18)} ${t.direction} ${t.tradingsymbol} x${t.lots} ${t.tier} pnl=${t.realized_pnl ?? "—"}`).join("\n")
        : "no trades yet";
      const events = await (await fetch(`${API}/risk-events?limit=25`)).json();
      document.getElementById("desk-fb-events").textContent = events.length
        ? events.map((e) => `${(e.created_at || "").slice(11, 19)} ${e.event.padEnd(14)} ${e.from_status}→${e.to_status} ${e.actor} ${e.reason}`).join("\n")
        : "no events yet";
    } catch { /* offline */ }
  }
  refresh();
  setInterval(refresh, 3000);
}

async function mountPanel() {
  const [React, ReactDOM, ui] = await Promise.all([
    import("react"),
    import("react-dom/client"),
    import("optionsdesk-ui"),
  ]);
  const shadow = host.attachShadow({ mode: "open" });
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "/static/desk/optionsdesk-ui.css";
  const theme = document.createElement("style");
  theme.textContent = THEME;
  const mount = document.createElement("div");
  shadow.append(css, theme, mount);
  await new Promise((resolve) => { css.onload = resolve; css.onerror = resolve; setTimeout(resolve, 1500); });
  ReactDOM.createRoot(mount).render(
    React.createElement(ui.DeskPanel, { apiBase: API, actor: "operator", pollMs: 2000, showStrategies: true }),
  );
}

(async () => {
  fetchStatus();
  setInterval(fetchStatus, 4000);
  try {
    await mountPanel();
  } catch (e) {
    mountFallback(e && e.message ? e.message : "module load failed");
  }
})();
