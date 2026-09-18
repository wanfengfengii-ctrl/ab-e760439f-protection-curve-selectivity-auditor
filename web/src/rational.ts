/** 精确解析 API 返回的约分有理数字符串，渲染时才降级为 number。 */

export interface Rational {
  num: bigint;
  den: bigint;
}

export function parseRational(text: string): Rational {
  const match = /^(-?\d+)(?:\/(\d+))?$/.exec(text.trim());
  if (!match) {
    throw new Error(`非法有理数: ${text}`);
  }
  const num = BigInt(match[1]);
  const den = match[2] ? BigInt(match[2]) : 1n;
  if (den === 0n) {
    throw new Error(`分母为零: ${text}`);
  }
  return { num, den };
}

export function toNumber(value: Rational): number {
  return Number(value.num) / Number(value.den);
}

/** 精确比较两个有理数：a<b 返回 -1，相等返回 0，a>b 返回 1。 */
export function compareRational(a: Rational, b: Rational): number {
  const diff = a.num * b.den - b.num * a.den;
  return diff < 0n ? -1 : diff > 0n ? 1 : 0;
}

/** 解析并转成 number，仅供 SVG 坐标换算，绝不回传给判定逻辑。 */
export function parseToNumber(text: string): number {
  return toNumber(parseRational(text));
}
