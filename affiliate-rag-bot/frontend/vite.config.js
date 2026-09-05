import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API calls to the FastAPI backend so `npm run dev` (with
// hot-module-reload) and uvicorn run side by side. Production build lands in
// `dist/`, which FastAPI serves directly.
const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/docs": { target: BACKEND, changeOrigin: true },
      "/openapi.json": { target: BACKEND, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
