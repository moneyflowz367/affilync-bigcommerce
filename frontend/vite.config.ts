import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3006,
    proxy: {
      '/api': {
        target: 'http://localhost:8006',
        changeOrigin: true,
      },
      '/oauth': {
        target: 'http://localhost:8006',
        changeOrigin: true,
      },
      '/webhooks': {
        target: 'http://localhost:8006',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
