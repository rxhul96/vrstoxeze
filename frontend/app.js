(() => {
  const $ = (id) => document.getElementById(id);
  const state = {
    win: "overview",
    snapshot: null,
    chainRows: [],
    atm: 0,
    depth: 3,
    rowH: 24,
    overscan: 6,
    chart: null,
    series: null,
    logicalRange: null,
    overlayDirty: false,
    seeded: false,
  };

  function showWin(name) {
    state.win = name;
    document.querySelectorAll(".term-win").forEach((el) => el.classList.toggle("on", el.dataset.win === name));
    document.querySelectorAll(".term-nav button").forEach((b) => b.classList.toggle("on", b.dataset.win === name));
    sizeChart();
    if (name === "chain") mountFullChain();
  }
  document.getElementById("term-nav").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-win]");
    if (b) showWin(b.dataset.win);
  });

  function clsNum(n) {
    if (n == null || Number.isNaN(n)) return "";
    return n > 0 ? "up" : n < 0 ? "down" : "";
  }
  function fmt(n, d = 2) {
    if (n == null || Number.isNaN(n)) return "—";
    return Number(n).toFixed(d);
  }

  function paintHeader(s) {
    $("m-ltp").textContent = fmt(s.spot, 2);
    $("m-chg").textContent = fmt(s.change, 2);
    $("m-chg").className = clsNum(s.change);
    $("m-pct").textContent = fmt(s.pct, 2) + "%";
    $("m-pct").className = clsNum(s.pct);
    $("m-vwap").textContent = fmt(s.vwap, 2);
    $("m-regime").textContent = s.regime || "—";
    $("m-bias").textContent = s.bias || "—";
    $("m-bias").className = s.bias === "BULLISH" ? "up" : s.bias === "BEARISH" ? "down" : "";
    $("m-score").textContent = fmt(s.score, 1);
    $("m-conf").textContent = s.confidence != null ? Math.round(s.confidence * 100) + "%" : "—";
    $("m-live").textContent = s.spot ? "LIVE" : "WAIT";
  }

  function paintSignal(sig) {
    if (!sig) return;
    $("sig-dir").textContent = sig.direction || "NO SIGNAL";
    $("sig-dir").className = "sig-dir " + (sig.direction === "BULLISH" || sig.signal_type === "CALL BUY BIAS" ? "up" : sig.direction === "BEARISH" || sig.signal_type === "PUT BUY BIAS" ? "down" : "");
    $("sig-type").textContent = sig.signal_type || "";
    $("sig-conf").textContent = sig.confidence != null ? Math.round(sig.confidence * 100) + "%" : "—";
    $("sig-score").textContent = fmt(sig.score, 1);
    const ez = sig.entry_zone;
    $("sig-entry").textContent = ez ? `${ez.low}–${ez.high}` : "—";
    $("sig-t1").textContent = sig.target_1 ?? "—";
    $("sig-t2").textContent = sig.target_2 ?? "—";
    $("sig-inv").textContent = sig.invalidation ?? "—";
    $("sig-rr").textContent = sig.risk_reward ?? "—";
    $("sig-state").textContent = sig.state || "WATCHING";
    $("sig-reasons").innerHTML = (sig.reasons || []).map((r) => `<li>${r}</li>`).join("");
    $("sig-conflicts").innerHTML = (sig.conflicts || []).length
      ? (sig.conflicts || []).map((r) => `<li>${r}</li>`).join("")
      : "<li>none</li>";
    $("signals-full").innerHTML = $("signal-card").innerHTML;
  }

  function visibleRows() {
    const depth = Number($("chain-depth").value);
    const rows = state.chainRows;
    if (!rows.length) return [];
    const atmIdx = rows.findIndex((r) => r.atm);
    if (depth === 0) return atmIdx >= 0 ? [rows[atmIdx]] : rows.slice(0, 1);
    if (atmIdx < 0) return rows;
    return rows.slice(Math.max(0, atmIdx - depth), atmIdx + depth + 1);
  }

  function barHtml(intensity, kind, side) {
    const w = Math.min(100, Math.abs(intensity) * 100);
    return `<div class="oi-bar ${side} ${kind === "unwind" ? "out" : kind === "buildup" ? "in" : ""}"><i style="width:${w}%"></i></div>`;
  }

  function paintChainRow(r, heat) {
    const h = heat || {};
    const atm = r.atm ? "atm" : "";
    return `<tr class="${atm}" data-strike="${r.strike}">
      <td>${barHtml(h.ce_intensity || 0, h.ce_kind, "ce")}</td>
      <td>${r.ce.oi}</td><td class="${clsNum(r.ce.doi)}">${r.ce.doi}</td>
      <td>${r.ce.vol}</td><td>${fmt(r.ce.ltp, 1)}</td>
      <td class="strike-col">${r.strike}</td>
      <td>${fmt(r.pe.ltp, 1)}</td><td>${r.pe.vol}</td>
      <td class="${clsNum(r.pe.doi)}">${r.pe.doi}</td><td>${r.pe.oi}</td>
      <td>${barHtml(h.pe_intensity || 0, h.pe_kind, "pe")}</td>
    </tr>`;
  }

  function renderChainVirtual(scrollEl, bodyEl) {
    const rows = visibleRows();
    const heat = (state.snapshot && state.snapshot.heatmap) || [];
    const heatMap = Object.fromEntries(heat.map((h) => [h.strike, h]));
    const h = state.rowH;
    const view = scrollEl.clientHeight;
    const total = rows.length * h;
    const top = scrollEl.scrollTop;
    const start = Math.max(0, Math.floor(top / h) - state.overscan);
    const end = Math.min(rows.length, Math.ceil((top + view) / h) + state.overscan);
    const slice = rows.slice(start, end);
    $("chain-spacer-top").style.height = start * h + "px";
    $("chain-spacer-bot").style.height = Math.max(0, total - end * h) + "px";
    bodyEl.innerHTML = slice.map((r) => paintChainRow(r, heatMap[r.strike])).join("");
  }

  function renderChain() {
    const scroll = $("chain-scroll");
    const body = $("chain-body");
    if (!scroll || !body) return;
    renderChainVirtual(scroll, body);
  }

  function centerAtm() {
    const rows = visibleRows();
    const idx = rows.findIndex((r) => r.atm);
    const scroll = $("chain-scroll");
    if (idx < 0) return;
    scroll.scrollTop = Math.max(0, idx * state.rowH - scroll.clientHeight / 2 + state.rowH);
    renderChain();
  }

  $("chain-scroll").addEventListener("scroll", () => renderChain(), { passive: true });
  $("chain-scroll").addEventListener("keydown", (e) => {
    const el = $("chain-scroll");
    if (e.key === "Home") { el.scrollTop = 0; e.preventDefault(); }
    if (e.key === "End") { el.scrollTop = el.scrollHeight; e.preventDefault(); }
    if (e.key === "PageDown") { el.scrollTop += el.clientHeight; e.preventDefault(); }
    if (e.key === "PageUp") { el.scrollTop -= el.clientHeight; e.preventDefault(); }
  });
  $("chain-depth").addEventListener("change", () => { state.depth = Number($("chain-depth").value); renderChain(); });
  $("btn-atm").addEventListener("click", centerAtm);

  function mountFullChain() {
    const host = $("chain-scroll-full");
    if (!host.dataset.ready) {
      host.innerHTML = $("chain-scroll").innerHTML;
      host.dataset.ready = "1";
    }
  }

  function boxes(el, items) {
    el.innerHTML = items.map(([k, v]) => `<div class="oc-sum-box"><span>${k}</span><b>${v}</b></div>`).join("");
  }

  function paintRest(s) {
    const cvd = s.cvd || {};
    $("cvd-badge").textContent = cvd.methodology || "ESTIMATED CVD";
    $("cvd-note").textContent = cvd.methodology_note || "";
    boxes($("cvd-boxes"), [
      ["Buy vol", cvd.buy_volume], ["Sell vol", cvd.sell_volume], ["Delta", cvd.delta],
      ["CVD", cvd.cumulative_delta], ["Slope", cvd.slope], ["Accel", cvd.acceleration],
      ["Label", cvd.label], ["Bias", cvd.bias], ["Event", cvd.event || "—"],
    ]);
    const p = s.pcr || {};
    boxes($("pcr-boxes"), [
      ["OI PCR", p.oi_pcr], ["Vol PCR", p.volume_pcr], ["ATM PCR", p.atm_pcr],
      ["Nearby", p.nearby_pcr], ["Trend", p.trend], ["Accel", p.acceleration],
      ["Session Δ", p.session_change],
    ]);
    $("pcr-note").textContent = p.note || "";
    const ta = s.ta || {};
    boxes($("vol-boxes"), [
      ["RVOL", ta.rvol], ["Spike", ta.volume_spike], ["VWAP", ta.vwap],
      ["EMA20", ta.ema20], ["EMA50", ta.ema50], ["RSI", ta.rsi], ["ATR", ta.atr],
      ["Structure", ta.structure], ["Event", ta.event || "—"],
    ]);
    boxes($("st-boxes"), [
      ["Regime", s.regime], ["Bias", s.bias], ["Score", s.score],
      ["VWAP", ta.vwap], ["Structure", ta.structure],
    ]);
    $("ict-json").textContent = JSON.stringify(s.ict || {}, null, 2);
    const heat = s.heatmap || [];
    $("oi-heat").innerHTML = heat.map((h) => {
      const ceW = Math.abs(h.ce_intensity) * 100;
      const peW = Math.abs(h.pe_intensity) * 100;
      return `<div class="heat-row">
        <div class="heat-bar"><i class="${h.ce_kind === "unwind" ? "out" : "in"}" style="width:${ceW}%;margin-left:auto;background:${h.ce_kind === "unwind" ? "var(--red)" : "var(--green)"}"></i></div>
        <div class="strike-col">${h.strike}${h.resistance ? " R" : ""}${h.support ? " S" : ""}</div>
        <div class="heat-bar"><i style="width:${peW}%;background:${h.pe_kind === "unwind" ? "var(--red)" : "var(--green)"}"></i></div>
      </div>`;
    }).join("");
    $("news-list").innerHTML = (s.news || []).map((n) =>
      `<div class="news-item"><div class="src">${n.source} · ${n.sentiment} · rel ${n.effective_relevance}</div>${n.headline}</div>`
    ).join("");
    const m = s.master || {};
    $("ai-master").innerHTML = `<b>${m.headline || ""}</b><div>${m.narrative || ""}</div><div>conflicts: ${(m.conflicts || []).join(", ") || "none"}</div>`;
    $("ai-list").innerHTML = (s.specialists || []).map((a) =>
      `<div class="ai-row"><span>${a.name}</span><b>${a.bias}</b></div>`
    ).join("");
  }

  function initChart() {
    const el = $("chart");
    state.chart = LightweightCharts.createChart(el, {
      layout: { background: { color: "#0b0e11" }, textColor: "#7b8796" },
      grid: { vertLines: { color: "#1a212b" }, horzLines: { color: "#1a212b" } },
      rightPriceScale: { borderColor: "#2a3340" },
      timeScale: { borderColor: "#2a3340", timeVisible: true },
      crosshair: { mode: 0 },
    });
    state.series = state.chart.addCandlestickSeries({
      upColor: "#3dcc8a", downColor: "#ee6b73", borderVisible: false,
      wickUpColor: "#3dcc8a", wickDownColor: "#ee6b73",
    });
    state.chart.timeScale().subscribeVisibleLogicalRangeChange((r) => {
      state.logicalRange = r;
      // Viewport only — never refetch or rebuild the chain.
    });
    $("btn-fit").onclick = () => state.chart.timeScale().fitContent();
    $("btn-reset").onclick = () => { state.logicalRange = null; state.chart.timeScale().fitContent(); };
    const niftyHost = $("nifty-chart");
    state.niftyChart = LightweightCharts.createChart(niftyHost, {
      layout: { background: { color: "#0b0e11" }, textColor: "#7b8796" },
      grid: { vertLines: { color: "#1a212b" }, horzLines: { color: "#1a212b" } },
    });
    state.niftySeries = state.niftyChart.addCandlestickSeries({
      upColor: "#3dcc8a", downColor: "#ee6b73", borderVisible: false,
      wickUpColor: "#3dcc8a", wickDownColor: "#ee6b73",
    });
  }

  function sizeChart() {
    if (!state.chart) return;
    const el = $("chart");
    state.chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
    if (state.logicalRange) state.chart.timeScale().setVisibleLogicalRange(state.logicalRange);
    const n = $("nifty-chart");
    if (n && state.niftyChart) state.niftyChart.applyOptions({ width: n.clientWidth, height: n.clientHeight });
  }
  window.addEventListener("resize", sizeChart);

  function applyCandle(c) {
    if (!c || !state.series) return;
    const pt = { time: c.time, open: c.open, high: c.high, low: c.low, close: c.close };
    state.series.update(pt);
    state.niftySeries.update(pt);
  }

  function ingest(s) {
    state.snapshot = s;
    if (s.chain && s.chain.rows) {
      state.chainRows = s.chain.rows;
      state.atm = s.chain.atm;
    }
    paintHeader(s);
    paintSignal(s.signal);
    paintRest(s);
    if (s.candles && s.candles.length && !state.seeded) {
      const data = s.candles.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close }));
      state.series.setData(data);
      state.niftySeries.setData(data);
      state.seeded = true;
      state.chart.timeScale().fitContent();
    } else if (s.candle) {
      applyCandle(s.candle);
    }
    renderChain();
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onopen = () => { $("st-ws").textContent = "WebSocket ok"; $("st-ws").className = "ok"; };
    ws.onmessage = (e) => ingest(JSON.parse(e.data));
    ws.onclose = () => { $("st-ws").textContent = "WebSocket down"; $("st-ws").className = "bad"; setTimeout(connect, 1500); };
  }

  async function pollHealth() {
    try {
      const h = await (await fetch("/api/health")).json();
      const set = (id, key) => {
        const el = $(id);
        el.textContent = `${key} ${h[key] || "—"}`;
        el.className = h[key] === "ok" ? "ok" : h.stale ? "warn" : "";
      };
      set("st-kite", "kite");
      $("st-data").textContent = h.stale ? "Data STALE" : "Data ok";
      $("st-data").className = h.stale ? "warn" : "ok";
      set("st-opt", "options");
      set("st-cvd", "cvd");
      set("st-news", "news");
      set("st-ai", "ai");
      $("st-srv").textContent = `Server ${h.database}`;
      $("st-lat").textContent = `latency ${h.latency_ms ?? "—"}ms`;
      $("st-upd").textContent = `last ${h.last_update || "—"}`;
      if (h.signals_paused) $("m-live").textContent = "SIGNALS PAUSED";
      boxes($("health-boxes"), Object.entries(h).filter(([k]) => typeof h[k] !== "object").map(([k, v]) => [k, v]));
      const st = await (await fetch("/api/status")).json();
      $("session-meta").textContent = JSON.stringify(st, null, 2);
      $("ov-state").textContent = st.session?.phase || "";
    } catch {
      $("st-srv").textContent = "Server down";
    }
  }

  // Splitters — viewport only.
  function dragSplit(el, onMove) {
    el.addEventListener("mousedown", (e) => {
      e.preventDefault();
      const move = (ev) => onMove(ev);
      const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); sizeChart(); };
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    });
  }
  dragSplit($("split-h"), (ev) => {
    const dock = document.querySelector(".dock");
    const rect = dock.getBoundingClientRect();
    const y = ev.clientY - rect.top;
    document.querySelector(".dock-chart").style.flexBasis = y + "px";
    sizeChart();
  });
  dragSplit($("split-v"), (ev) => {
    const bottom = document.querySelector(".dock-bottom");
    const rect = bottom.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    document.querySelector(".dock-chain").style.flexBasis = x + "px";
  });

  initChart();
  sizeChart();
  connect();
  fetch("/api/snapshot").then((r) => r.json()).then((s) => { if (s && s.spot) ingest(s); }).catch(() => {});
  fetch("/api/session/replay").then((r) => r.json()).then((rep) => {
    if (rep.snapshot && rep.snapshot.spot) ingest(rep.snapshot);
  }).catch(() => {});
  setInterval(pollHealth, 4000);
  pollHealth();
})();
