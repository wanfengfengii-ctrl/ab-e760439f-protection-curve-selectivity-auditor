import { expect, test } from '@playwright/test';

// 与 README 数据约定一致的真实联调载荷
const FAIL_PAYLOAD = JSON.stringify({
  window: { start: 1000, end: 5000 },
  margin: 200,
  upstream: {
    id: 'QS-main',
    points: [
      { current: 500, time: 10000 },
      { current: 6000, time: 1000 },
    ],
  },
  downstream: [
    {
      id: 'QF-feeder-1',
      points: [
        { current: 500, time: 1000 },
        { current: 6000, time: 6000 },
      ],
    },
    {
      id: 'QF-feeder-2',
      points: [
        { current: 500, time: 2000 },
        { current: 6000, time: 1500 },
      ],
    },
  ],
});

const PASS_PAYLOAD = JSON.stringify({
  window: { start: 1000, end: 5000 },
  margin: 0,
  upstream: {
    id: 'QS-main',
    points: [
      { current: 500, time: 100000 },
      { current: 6000, time: 100000 },
    ],
  },
  downstream: [
    {
      id: 'QF-feeder-1',
      points: [
        { current: 500, time: 1000 },
        { current: 6000, time: 6000 },
      ],
    },
    {
      id: 'QF-feeder-2',
      points: [
        { current: 500, time: 2000 },
        { current: 6000, time: 1500 },
      ],
    },
  ],
});

const INVALID_PAYLOAD = JSON.stringify({
  window: { start: 1000, end: 5000 },
  margin: -3,
  upstream: {
    id: 'dup',
    points: [
      { current: 500, time: 10000 },
      { current: 6000, time: 1000 },
    ],
  },
  downstream: [
    {
      id: 'dup',
      points: [
        { current: 500, time: 1000 },
        { current: 6000, time: 6000 },
      ],
    },
    {
      id: 'QF-feeder-2',
      points: [{ current: 500, time: 2000 }],
    },
  ],
});

test('合法提交：精确有理数边界、SVG 叠绘与悬停高亮', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('json-input').fill(FAIL_PAYLOAD);
  await page.getByTestId('submit-button').click();

  await expect(page.getByTestId('verdict-banner')).toContainText('审查未通过');
  const row = page.getByTestId('interval-row');
  await expect(row).toHaveCount(1);
  // 边界必须与 API 的约分有理数完全一致
  await expect(row).toContainText('27700/7');
  await expect(row).toContainText('5000');
  await expect(row).toContainText('-27000/11');
  await expect(row).toContainText('QF-feeder-1');

  await expect(page.getByTestId('chart')).toBeVisible();
  await expect(page.getByTestId('curve-QS-main')).toBeVisible();
  await expect(page.getByTestId('curve-QF-feeder-1')).toBeVisible();
  await expect(page.getByTestId('curve-QF-feeder-2')).toBeVisible();

  const band = page.getByTestId('violation-band-0');
  await expect(band).toHaveAttribute('data-highlighted', 'false');
  await row.hover();
  await expect(band).toHaveAttribute('data-highlighted', 'true');
});

test('整批拒绝：展示全部错误且不残留旧图', async ({ page }) => {
  await page.goto('/');
  // 先渲染一次合法结果
  await page.getByTestId('json-input').fill(FAIL_PAYLOAD);
  await page.getByTestId('submit-button').click();
  await expect(page.getByTestId('chart')).toBeVisible();
  // 再提交非法载荷：旧图必须被清除
  await page.getByTestId('json-input').fill(INVALID_PAYLOAD);
  await page.getByTestId('submit-button').click();

  await expect(page.getByTestId('error-panel')).toBeVisible();
  const items = page.getByTestId('error-item');
  await expect(items).toHaveCount(3);
  await expect(items.nth(0)).toContainText('margin');
  await expect(items.nth(1)).toContainText('duplicate_id');
  await expect(items.nth(2)).toContainText('too_few_points');
  await expect(page.getByTestId('chart')).toHaveCount(0);
  await expect(page.getByTestId('verdict-banner')).toHaveCount(0);
});

test('全窗安全：明确显示通过', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('json-input').fill(PASS_PAYLOAD);
  await page.getByTestId('submit-button').click();
  await expect(page.getByTestId('verdict-banner')).toContainText('审查通过');
  await expect(page.getByTestId('interval-row')).toHaveCount(0);
});
