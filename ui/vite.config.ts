import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Standalone build: emits into the Python package so `uvicorn optionsdesk.app` can serve it.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../src/optionsdesk/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/desk": process.env.DESK_API_URL ?? "http://localhost:8000",
      "/healthz": process.env.DESK_API_URL ?? "http://localhost:8000",
    },
  },
});
