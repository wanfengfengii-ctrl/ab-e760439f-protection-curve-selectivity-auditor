import { describe, expect, it } from 'vitest';
import type { AnalysisResponse, Protector } from '../types';
import {
  curvePointsInWindow,
  envelopePoints,
  interpolateTime,
  makeScales,
  toPixelPoints,
} from './geometry';

const c: Protector = {
  id: 'X',
  points: [
    { current: 1, time: 10 },
    { current: 7, time: 4 },
  ],
};

describe('interpolateTime', () => {
  it('在折点处取原值，区间内按电流线性插值', () => {
    expect(interpolateTime(c, 1)).toBe(10);
    expect(interpolateTime(c, 7)).toBe(4);
    // U(x)=11-x -> x=4 时 7。
    expect(interpolateTime(c, 4)).toBeCloseTo(7);
  });

  it('窗边界外按端值钳制（覆盖已保证时不会用到）', () => {
    expect(interpolateTime(c, 0)).toBe(10);
    expect(interpolateTime(c, 9)).toBe(4);
  });
});

describe('curvePointsInWindow', () => {
  it('两端补到窗边界且包含内部折点', () => {
    const multi: Protector = {
      id: 'M',
      points: [
        { current: 1, time: 2 },
        { current: 3, time: 8 },
        { current: 10, time: 2 },
      ],
    };
    const pts = curvePointsInWindow(multi, 1, 10);
    expect(pts.map((p) => p.x)).toEqual([1, 3, 10]);
    expect(pts[1].y).toBe(8);
  });
});

describe('envelopePoints', () => {
  it('把有理端点逐段连成闭合折线', () => {
    const resp: AnalysisResponse = {
      safe: false,
      intervals: [],
      window: { lo: 1, hi: 4 },
      envelope: [
        {
          lo: { num: 1, den: 1 },
          hi: { num: 7, den: 2 },
          lo_time: { num: 4, den: 1 },
          hi_time: { num: 4, den: 1 },
          responsible: 'D1',
        },
        {
          lo: { num: 7, den: 2 },
          hi: { num: 4, den: 1 },
          lo_time: { num: 4, den: 1 },
          hi_time: { num: 8, den: 1 },
          responsible: 'D2',
        },
      ],
    };
    const pts = envelopePoints(resp);
    expect(pts).toHaveLength(3);
    expect(pts[0]).toEqual({ x: 1, y: 4 });
    expect(pts[1].x).toBeCloseTo(3.5);
    expect(pts[2]).toEqual({ x: 4, y: 8 });
  });
});

describe('makeScales', () => {
  it('把窗边界映射到绘图区左右，y=0 映射到底部', () => {
    const s = makeScales(800, 400, 1, 7, [c], []);
    expect(s.sx(1)).toBeCloseTo(s.padL);
    expect(s.sx(7)).toBeCloseTo(800 - s.padR);
    expect(s.sy(0)).toBeCloseTo(400 - s.padB);
    // y 越大像素越靠上。
    expect(s.sy(10)).toBeLessThan(s.sy(0));
  });

  it('toPixelPoints 输出可用于 SVG 的坐标串', () => {
    const s = makeScales(800, 400, 1, 7, [c], []);
    const str = toPixelPoints([{ x: 1, y: 10 }, { x: 7, y: 4 }], s);
    expect(str.split(' ')).toHaveLength(2);
    expect(str).toContain(',');
  });

  it('零宽度窗不除零，单点居中映射', () => {
    const s = makeScales(800, 400, 4, 4, [c], []);
    // 显示域对称扩展为 [3,5]，x=4 恰在绘图区水平中央。
    const center = s.padL + (800 - s.padL - s.padR) / 2;
    expect(s.sx(4)).toBeCloseTo(center);
    expect(Number.isFinite(s.sx(4))).toBe(true);
  });
});
