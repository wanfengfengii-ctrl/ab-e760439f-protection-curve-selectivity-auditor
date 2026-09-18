import { defineConfig, devices } from '@playwright/test';

// 真实联调：同时拉起 FastAPI(8000) 与 Vite dev server(5173)，
// 浏览器走 Vite 代理访问 /api，与生产 nginx 反代行为一致。
export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:5173',
  },
  webServer: [
    {
      command: '/workspace/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: '../api',
      port: 8000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --port 5173 --strictPort',
      port: 5173,
      reuseExistingServer: !process.env.CI,
    },
  ],
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
