/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In dev, Vite plays the role of the gateway: it routes /api/<service>/* to
// the service running locally, stripping the prefix, exactly like the
// Kubernetes Gateway and the docker-compose gateway do.
const route = (target: string, prefix: string) => ({
  target,
  changeOrigin: true,
  rewrite: (path: string) => path.replace(new RegExp(`^${prefix}`), ''),
});

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/catalog': route('http://localhost:3000', '/api/catalog'),
      '/api/orders': route('http://localhost:8000', '/api/orders'),
    },
  },
  build: {
    sourcemap: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
});
