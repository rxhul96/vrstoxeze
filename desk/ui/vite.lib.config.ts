import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Library build: `import { DeskPanel } from "optionsdesk-ui"` inside the host React app.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "dist-lib",
    emptyOutDir: true,
    cssCodeSplit: false,
    lib: {
      entry: "src/lib.ts",
      name: "OptionsDeskUI",
      formats: ["es"],
      fileName: () => "optionsdesk-ui.js",
    },
    rollupOptions: {
      external: ["react", "react-dom", "react/jsx-runtime"],
      output: { assetFileNames: "optionsdesk-ui[extname]" },
    },
  },
});
