import { describe, expect, it } from 'vitest';
import { compareRational, parseRational, parseToNumber, toNumber } from '../rational';

describe('parseRational', () => {
  it('解析整数字符串', () => {
    expect(parseRational('5000')).toEqual({ num: 5000n, den: 1n });
  });

  it('解析分数字符串', () => {
    expect(parseRational('28250/7')).toEqual({ num: 28250n, den: 7n });
  });

  it('解析负分数', () => {
    expect(parseRational('-27000/11')).toEqual({ num: -27000n, den: 11n });
  });

  it('拒绝非法输入', () => {
    expect(() => parseRational('1.5')).toThrow('非法有理数');
    expect(() => parseRational('abc')).toThrow('非法有理数');
    expect(() => parseRational('1/0')).toThrow('分母为零');
  });
});

describe('compareRational', () => {
  it('精确比较，不受浮点误差影响', () => {
    expect(compareRational(parseRational('1/3'), parseRational('2/6'))).toBe(0);
    expect(compareRational(parseRational('28250/7'), parseRational('4035'))).toBe(1);
    expect(compareRational(parseRational('-27000/11'), parseRational('0'))).toBe(-1);
  });
});

describe('toNumber / parseToNumber', () => {
  it('转换为渲染用浮点', () => {
    expect(toNumber(parseRational('28250/7'))).toBeCloseTo(4035.714285, 5);
    expect(parseToNumber('5000')).toBe(5000);
  });
});
