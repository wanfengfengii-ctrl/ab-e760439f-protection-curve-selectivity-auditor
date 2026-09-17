import { expect, test, type Page } from '@playwright/test';

const editor = (page: Page) => page.getByLabel('审查输入 JSON 编辑器');
const submit = (page: Page) => page.getByRole('button', { name: '提交审查' });

async function loadScenario(page: Page, obj: unknown) {
  await editor(page).fill(JSON.stringify(obj));
  await submit(page).click();
}

// U(x)=11-x，D1 恒 5，D2 恒 1，窗 [1,7]，裕量 0 -> 非选择 [6,7]。
const crossing = {
  window: { lo: 1, hi: 7 },
  margin: 0,
  upstream: { id: 'U', points: [{ current: 1, time: 10 }, { current: 7, time: 4 }] },
  downstream: [
    { id: 'D1', points: [{ current: 1, time: 5 }, { current: 7, time: 5 }] },
    { id: 'D2', points: [{ current: 1, time: 1 }, { current: 7, time: 1 }] },
  ],
};

test('初始为占位态，提交后显示非选择区间与精确整数边界', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByTestId('placeholder')).toBeVisible();

  await loadScenario(page, crossing);

  await expect(page.getByTestId('result-panel')).toBeVisible();
  const row = page.getByTestId('interval-row-0');
  await expect(row).toContainText('[6, 7]');
  await expect(row).toContainText('D1');

  // SVG 叠绘：2 下级 + 1 上级 + 1 包络，共 4 条折线。
  expect(await page.locator('svg.chart polyline').count()).toBe(4);
  // 非选择区间以红色矩形带绘制。
  expect(await page.locator('svg.chart rect[fill="#ef4444"]').count()).toBeGreaterThan(0);
});

test('全窗安全时明确显示通过横幅', async ({ page }) => {
  await page.goto('/');
  await loadScenario(page, {
    window: { lo: 1, hi: 10 },
    margin: 0,
    upstream: { id: 'U', points: [{ current: 1, time: 100 }, { current: 10, time: 100 }] },
    downstream: [
      { id: 'D1', points: [{ current: 1, time: 10 }, { current: 10, time: 10 }] },
      { id: 'D2', points: [{ current: 1, time: 5 }, { current: 10, time: 5 }] },
    ],
  });
  await expect(page.getByTestId('safe-banner')).toBeVisible();
  await expect(page.getByTestId('safe-banner')).toContainText('审查通过');
});

test('分数交叉边界 7/2 精确显示，不被采样漏掉', async ({ page }) => {
  await page.goto('/');
  await loadScenario(page, {
    window: { lo: 1, hi: 4 },
    margin: 0,
    upstream: { id: 'U', points: [{ current: 1, time: 7 }, { current: 4, time: 7 }] },
    downstream: [
      { id: 'D1', points: [{ current: 1, time: 2 }, { current: 4, time: 8 }] },
      { id: 'D2', points: [{ current: 1, time: 1 }, { current: 4, time: 1 }] },
    ],
  });
  const row = page.getByTestId('interval-row-0');
  await expect(row).toContainText('7/2');
  await expect(row).toContainText('D1');
});

test('整批拒绝：一次列出多处错误并清空旧图，不残留', async ({ page }) => {
  await page.goto('/');
  // 先得到一张合法图。
  await loadScenario(page, crossing);
  await expect(page.getByTestId('chart-panel')).toBeVisible();

  // 再提交含两处错误的输入。
  const bad = JSON.parse(JSON.stringify(crossing));
  bad.margin = -1;
  bad.downstream[0].points[0].current = 0;
  await loadScenario(page, bad);

  const errorPanel = page.getByTestId('error-panel');
  await expect(errorPanel).toBeVisible();
  await expect(errorPanel).toContainText('/margin');
  await expect(errorPanel).toContainText('/downstream/0/points/0/current');

  // 旧图必须消失，回到占位态。
  await expect(page.getByTestId('chart-panel')).toHaveCount(0);
  await expect(page.getByTestId('placeholder')).toBeVisible();
});

test('本地非法 JSON 不发请求并提示，同样不残留旧图', async ({ page }) => {
  await page.goto('/');
  await loadScenario(page, crossing);
  await editor(page).fill('{ 不是 json');
  await submit(page).click();
  await expect(page.getByTestId('local-error')).toBeVisible();
  await expect(page.getByTestId('chart-panel')).toHaveCount(0);
});

test('零长度相切接触以单点保留并标记', async ({ page }) => {
  await page.goto('/');
  await loadScenario(page, {
    window: { lo: 1, hi: 5 },
    margin: 1,
    upstream: {
      id: 'U',
      points: [{ current: 1, time: 9 }, { current: 2, time: 6 }, { current: 5, time: 9 }],
    },
    downstream: [
      { id: 'D1', points: [{ current: 1, time: 5 }, { current: 5, time: 5 }] },
      { id: 'D2', points: [{ current: 1, time: 1 }, { current: 5, time: 1 }] },
    ],
  });
  const row = page.getByTestId('interval-row-0');
  await expect(row).toContainText('[2, 2]');
  await expect(row).toContainText('零长度接触');
  // 图上以红色虚线（零长度）表示，而非普通矩形带。
  expect(await page.locator('svg.chart line[stroke-dasharray="3 3"]').count()).toBeGreaterThan(0);
});

test('悬停区间行联动高亮责任曲线与图中区间', async ({ page }) => {
  await page.goto('/');
  await loadScenario(page, crossing);
  const row = page.getByTestId('interval-row-0');

  // 悬停前责任下级 D1 是常规粗细 2。
  expect(await page.locator('svg.chart polyline[stroke-width="4.5"]').count()).toBe(0);

  await row.hover();
  await expect(row).toHaveClass(/hovered/);
  // 责任曲线 D1 被强调为 4.5，非责任曲线变细淡。
  expect(await page.locator('svg.chart polyline[stroke-width="4.5"]').count()).toBe(1);
});

test('通过文件上传 JSON 也能得到正确审查结果', async ({ page }) => {
  await page.goto('/');
  const safe = {
    window: { lo: 1, hi: 10 },
    margin: 0,
    upstream: { id: 'U', points: [{ current: 1, time: 100 }, { current: 10, time: 100 }] },
    downstream: [
      { id: 'D1', points: [{ current: 1, time: 10 }, { current: 10, time: 10 }] },
      { id: 'D2', points: [{ current: 1, time: 5 }, { current: 10, time: 5 }] },
    ],
  };
  await page
    .locator('input[type=file]')
    .setInputFiles({ name: 'case.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(safe)) });
  // 上传只填入文本框，仍需提交。
  await submit(page).click();
  await expect(page.getByTestId('safe-banner')).toBeVisible();
});
