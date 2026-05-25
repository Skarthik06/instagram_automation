import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // API + locally-rendered preview images both live on the backend.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/cdn': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});
