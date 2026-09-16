import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const SERVER_PORT = process.env.PORT || 3001;
const CLIENT_PORT = Number(process.env.CLIENT_PORT) || 5173;

// The React client lives in ./client and is built into ./client/dist.
// In development, Vite serves the client and proxies /api to the Express server.
export default defineConfig({
  root: 'client',
  plugins: [react()],
  server: {
    port: CLIENT_PORT,
    host: true,
    proxy: {
      '/api': {
        target: `http://localhost:${SERVER_PORT}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
