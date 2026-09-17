import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// dev / preview 都把 /api 与 /health 反代到 FastAPI，
// 因此浏览器始终用同源相对路径，生产环境由 nginx 做同样的事。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
  preview: {
    port: 4173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
});
