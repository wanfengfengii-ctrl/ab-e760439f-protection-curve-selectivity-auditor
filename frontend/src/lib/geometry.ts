import type { AnalysisResponse, Protector } from '../types';
import { rationalToNumber } from './rationals';

export type Pt = { x: number; y: number };

/** 在折点折线上求电流 x 处的线性插值时间（x 必须落在折点跨度内）。 */
export function interpolateTime(curve: Protector, x: number): number {
  const pts = curve.points;
  if (x <= pts[0].current) return pts[0].time;
  const last = pts[pts.length - 1];
  if (x >= last.current) return last.time;
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i];
    const b = pts[i + 1];
    if (x >= a.current && x <= b.current) {
      const t = (x - a.current) / (b.current - a.current);
      return a.time + t * (b.time - a.time);
    }
  }
  return last.time;
}

/**
 * 生成一条保护器在审查窗 [lo, hi] 内的折线数据点：
 * 首末补到窗边界（线性插值），中间包含所有折点。
 * 覆盖性已由后端保证，这里对合法输入闭合。
 */
export function curvePointsInWindow(
  curve: Protector,
  lo: number,
  hi: number,
): Pt[] {
  const inner = curve.points
    .filter((p) => p.current > lo && p.current < hi)
    .map((p) => ({ x: p.current, y: p.time }));
  return [
    { x: lo, y: interpolateTime(curve, lo) },
    ...inner,
    { x: hi, y: interpolateTime(curve, hi) },
  ];
}

/** 精确上包络在数据坐标中的折线点（端点为有理数转数值仅用于定位）。 */
export function envelopePoints(resp: AnalysisResponse): Pt[] {
  const pts: Pt[] = [];
  resp.envelope.forEach((seg, i) => {
    const x0 = rationalToNumber(seg.lo);
    const x1 = rationalToNumber(seg.hi);
    if (i === 0) pts.push({ x: x0, y: rationalToNumber(seg.lo_time) });
    pts.push({ x: x1, y: rationalToNumber(seg.hi_time) });
  });
  return pts;
}

export interface Scales {
  width: number;
  height: number;
  padL: number;
  padR: number;
  padT: number;
  padB: number;
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
  sx: (x: number) => number;
  sy: (y: number) => number;
}

/**
 * 依据所有曲线与包络的数据范围建立像素尺度。y 轴从 0 起（时间为正），
 * 顶端留出 8% 余量，保证曲线不贴边。
 */
export function makeScales(
  width: number,
  height: number,
  xMin: number,
  xMax: number,
  curves: Protector[],
  envelope: Pt[],
): Scales {
  const padL = 64;
  const padR = 20;
  const padT = 20;
  const padB = 40;
  let yMax = 0;
  for (const c of curves) for (const p of c.points) yMax = Math.max(yMax, p.time);
  for (const p of envelope) yMax = Math.max(yMax, p.y);
  yMax = yMax * 1.08 || 1;

  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  // 零宽度审查窗（单点查询）时对称扩展显示域，避免除零；数据本身不变。
  const domainSpan = xMax - xMin || 2;
  const domainLo = xMax - xMin === 0 ? xMin - 1 : xMin;
  const sx = (x: number) => padL + ((x - domainLo) / domainSpan) * plotW;
  const sy = (y: number) => padT + plotH - (y / yMax) * plotH;
  return {
    width, height, padL, padR, padT, padB,
    xMin, xMax, yMin: 0, yMax, sx, sy,
  };
}

/** 数据点序列转 SVG polyline 的 points 字符串。 */
export function toPixelPoints(pts: Pt[], s: Scales): string {
  return pts.map((p) => `${s.sx(p.x).toFixed(2)},${s.sy(p.y).toFixed(2)}`).join(' ');
}
