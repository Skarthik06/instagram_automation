import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Proxy target: inside Docker the backend is another container (http://backend:8000);
// running Vite on the host it's http://127.0.0.1:8000. Controlled by VITE_API_TARGET.
const API_TARGET = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,          // listen on 0.0.0.0 so the container port is reachable
    port: 3000,
    strictPort: true,
    watch: { usePolling: true },   // reliable HMR on Docker Desktop / Windows mounts
    proxy: {
      // API + locally-rendered preview images both live on the backend.
      '/api': { target: API_TARGET, changeOrigin: true },
      '/cdn': { target: API_TARGET, changeOrigin: true },
    },
  },
});
