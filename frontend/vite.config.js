import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // listen on all interfaces so Docker can expose the port
    port: 5173,
    strictPort: true,
    // Docker on Windows does not pass file-change events into containers, so poll instead.
    watch:
      process.env.VITE_USE_POLLING === 'true' ? { usePolling: true, interval: 300 } : undefined,
    // The browser calls /api on its own origin; Vite forwards those requests to FastAPI.
    proxy: {
      '/api': process.env.VITE_PROXY_TARGET || 'http://localhost:8000',
    },
  },
  build: {
    // The core app (React, router, icons) is ~500 kB before gzip (~155 kB gzipped); charts and
    // admin pages are already split off and loaded on demand.
    chunkSizeWarningLimit: 600,
  },
});
