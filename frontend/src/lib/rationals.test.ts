import { describe, expect, it } from 'vitest';
import {
  frac,
  rationalCompare,
  rationalToExactString,
  rationalToLabel,
  rationalToNumber,
} from './rationals';

describe('frac', () => {
  it('约分并令分母为正', () => {
    expect(frac(6, 4)).toEqual({ num: 3, den: 2 });
    expect(frac(-6, 4)).toEqual({ num: -3, den: 2 });
    expect(frac(6, -4)).toEqual({ num: -3, den: 2 });
    expect(frac(-6, -4)).toEqual({ num: 3, den: 2 });
  });

  it('分母为 0 时抛错', () => {
    expect(() => frac(1, 0)).toThrow();
  });
});

describe('显示', () => {
  it('整数不显示分母，分数显示精确式与近似', () => {
    expect(rationalToExactString({ num: 6, den: 1 })).toBe('6');
    expect(rationalToExactString({ num: 7, den: 2 })).toBe('7/2');
    const label = rationalToLabel({ num: 7, den: 2 });
    expect(label).toContain('7/2');
    expect(label).toContain('3.5');
  });

  it('数值转换正确', () => {
    expect(rationalToNumber({ num: 7, den: 2 })).toBeCloseTo(3.5);
  });
});

describe('rationalCompare', () => {
  it('精确比较分数而不丢精度', () => {
    expect(rationalCompare({ num: 1, den: 3 }, { num: 1, den: 2 })).toBe(-1);
    expect(rationalCompare({ num: 2, den: 3 }, { num: 2, den: 3 })).toBe(0);
    expect(rationalCompare({ num: 3, den: 2 }, { num: 1, den: 1 })).toBe(1);
    // 极大整数也不靠浮点：10^18/3 vs 333333333333333333
    expect(
      rationalCompare({ num: 1000000000000000000, den: 3 }, { num: 333333333333333333, den: 1 }),
    ).toBe(1);
  });
});
