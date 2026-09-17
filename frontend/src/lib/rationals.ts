import type { Rational } from '../types';

/** 有理数转浮点，仅用于 SVG 像素定位与小数近似显示；精确展示仍用 num/den。 */
export function rationalToNumber(r: Rational): number {
  return r.num / r.den;
}

/** 最大公约数（BigInt 无关，这里 num/den 已是安全整数）。 */
function gcd(a: number, b: number): number {
  a = Math.abs(a);
  b = Math.abs(b);
  while (b) [a, b] = [b, a % b];
  return a || 1;
}

/** 由两个整数构造已约分、分母为正的有理数。 */
export function frac(num: number, den: number): Rational {
  if (den === 0) throw new Error('分母不能为 0');
  if (den < 0) {
    num = -num;
    den = -den;
  }
  const g = gcd(num, den);
  return { num: num / g, den: den / g };
}

/** 精确分数文本：整数直接显示，否则显示 “num/den”。 */
export function rationalToExactString(r: Rational): string {
  if (r.den === 1) return String(r.num);
  return `${r.num}/${r.den}`;
}

/**
 * 精确又可读的文本：分数 + 括号内足够高精度的小数近似，
 * 让工程师同时看到精确边界与工程量级。小数只是近似，分数才是边界。
 */
export function rationalToLabel(r: Rational): string {
  const exact = rationalToExactString(r);
  if (r.den === 1) return exact;
  const approx = rationalToNumber(r);
  return `${exact} (≈${approx.toFixed(4)})`;
}

export function rationalCompare(a: Rational, b: Rational): number {
  // 交叉相乘，用 BigInt 避免任何溢出风险。
  const lhs = BigInt(a.num) * BigInt(b.den);
  const rhs = BigInt(b.num) * BigInt(a.den);
  return lhs < rhs ? -1 : lhs > rhs ? 1 : 0;
}
