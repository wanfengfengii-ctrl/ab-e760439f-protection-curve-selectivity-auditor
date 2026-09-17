import { afterEach, describe, expect, it, vi } from 'vitest';
import { analyze, formatPath } from './api';
import type { AnalysisResponse } from '../types';

const validBody: AnalysisResponse = {
  safe: true,
  intervals: [],
  envelope: [],
  window: { lo: 1, hi: 7 },
};

afterEach(() => vi.restoreAllMocks());

describe('analyze', () => {
  it('200 时返回归一化的成功结果', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(validBody), { status: 200 })));
    const r = await analyze({} as never);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.data.safe).toBe(true);
  });

  it('422 时返回按位置排列的错误数组', async () => {
    const errors = [
      { path: ['margin'], message: '裕量必须是非负整数' },
      { path: ['downstream', 0, 'points', 0, 'current'], message: '电流必须是正整数' },
    ];
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ errors }), { status: 422 })));
    const r = await analyze({} as never);
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.errors).toHaveLength(2);
      expect(r.errors[1].path).toEqual(['downstream', 0, 'points', 0, 'current']);
    }
  });

  it('网络不可达时归一化为单一错误而非抛出', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new Error('network down');
    }));
    const r = await analyze({} as never);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.errors[0].message).toContain('无法连接');
  });

  it('非 JSON 响应归一化为错误', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('oops', { status: 502 })));
    const r = await analyze({} as never);
    expect(r.ok).toBe(false);
  });
});

describe('formatPath', () => {
  it('渲染 JSON 指针风格位置', () => {
    expect(formatPath(['downstream', 0, 'points', 1, 'current'])).toBe(
      '/downstream/0/points/1/current',
    );
    expect(formatPath([])).toBe('(根)');
  });
});
