import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { DeskPanel } from "./DeskPanel";

const params = new URLSearchParams(window.location.search);
const apiBase = params.get("api") ?? import.meta.env.VITE_DESK_API_BASE ?? "/desk";
const token = params.get("token") ?? import.meta.env.VITE_DESK_API_TOKEN ?? undefined;
const actor = params.get("actor") ?? "operator";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <main className="mx-auto max-w-7xl p-4">
      <header className="mb-3 flex items-baseline justify-between">
        <h1 className="text-sm font-bold uppercase tracking-[0.2em] text-zinc-300">
          <span className="text-cyan-400">▮</span> Options Desk <span className="text-zinc-600">/ NFO governor</span>
        </h1>
        <span className="text-[10px] text-zinc-600">api {apiBase}</span>
      </header>
      <DeskPanel apiBase={apiBase} token={token} actor={actor} />
    </main>
  </StrictMode>,
);
