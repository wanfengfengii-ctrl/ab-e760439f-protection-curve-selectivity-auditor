import { defineConfig } from '@playwright/test';

// 真实联调：同时拉起 FastAPI(8000) 与 Vite 预览(4173)，
// 浏览器访问 4173，/api 与 /health 由 preview 反代到 8000（见 vite.config.ts）。
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    headless: true,
    // 在无特权 / 无用户命名空间的环境（PW_NO_SANDBOX=1）运行时禁用沙箱。
    // 浏览器进程默认继承本进程环境，因此本地解包库的 LD_LIBRARY_PATH 也会透传。
    launchOptions: process.env.PW_NO_SANDBOX
      ? { args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'] }
      : undefined,
  },
  webServer: [
    {
      command: './.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: 'npm run preview',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
