import type { DeskStatus, RiskEvent, SignalRecord, StrategyRecord, Trade } from "./types";

export class DeskApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export class DeskApi {
  constructor(
    private base: string = "/desk",
    private token?: string,
    private actor: string = "operator",
  ) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.token) headers["X-Desk-Token"] = this.token;
    const res = await fetch(`${this.base}${path}`, { ...init, headers });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
      } catch {
        /* ignore */
      }
      throw new DeskApiError(res.status, detail);
    }
    return (await res.json()) as T;
  }

  private post<T>(path: string, body: Record<string, unknown> = {}): Promise<T> {
    return this.request<T>(path, { method: "POST", body: JSON.stringify({ actor: this.actor, ...body }) });
  }

  status = () => this.request<DeskStatus>("/status");
  trades = (limit = 200) => this.request<Trade[]>(`/trades?limit=${limit}`);
  riskEvents = (limit = 200) => this.request<RiskEvent[]>(`/risk-events?limit=${limit}`);
  signals = (limit = 100) => this.request<SignalRecord[]>(`/signals?limit=${limit}`);
  strategies = () => this.request<StrategyRecord[]>("/strategies");

  arm = () => this.post("/arm", { confirm: true });
  disarm = () => this.post("/disarm");
  kill = (reason: string) => this.post("/kill", { reason });
  clearStop = (phrase: string, note: string) => this.post("/clear-stop", { phrase, note });
  confirmTrade = (id: number, phrase: string) => this.post<Trade>(`/trades/${id}/confirm`, { phrase });
  cancelTrade = (id: number) => this.post<Trade>(`/trades/${id}/cancel`);
  closeTrade = (id: number) => this.post<Trade>(`/trades/${id}/close`);
}
