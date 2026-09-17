import { useMemo } from 'react';
import type { AnalysisRequest, AnalysisResponse, Interval } from '../types';
import { rationalToNumber } from '../lib/rationals';
import {
  curvePointsInWindow,
  envelopePoints,
  makeScales,
  toPixelPoints,
  type Pt,
} from '../lib/geometry';

const WIDTH = 900;
const HEIGHT = 480;

const DOWNSTREAM_COLORS = ['#0d9488', '#7c3aed', '#c026d3', '#ea580c', '#65a30d'];

function colorFor(id: string, upstreamId: string, downstreamIds: string[]): string {
  if (id === upstreamId) return '#1d4ed8';
  const idx = downstreamIds.indexOf(id);
  return DOWNSTREAM_COLORS[(idx < 0 ? 0 : idx) % DOWNSTREAM_COLORS.length];
}

/** 生成 1/2/5 × 10^k 的“好看”刻度。 */
function niceTicks(min: number, max: number, count = 6): number[] {
  if (!(max > min)) return [min];
  const raw = (max - min) / (count - 1);
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / pow;
  const step = (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * pow;
  const start = Math.ceil(min / step) * step;
  const out: number[] = [];
  for (let v = start; v <= max + step * 1e-9; v += step) {
    out.push(Number(v.toFixed(10)));
  }
  return out;
}

interface ChartProps {
  request: AnalysisRequest;
  response: AnalysisResponse;
  hoveredIndex: number | null;
  onHoverIndex: (i: number | null) => void;
}

export function Chart({ request, response, hoveredIndex, onHoverIndex }: ChartProps) {
  const lo = request.window.lo;
  const hi = request.window.hi;

  const downstreamIds = request.downstream.map((d) => d.id);
  const envelope = useMemo(() => envelopePoints(response), [response]);
  const scales = useMemo(
    () => makeScales(WIDTH, HEIGHT, lo, hi, [request.upstream, ...request.downstream], envelope),
    [lo, hi, request, envelope],
  );

  const { sx, sy } = scales;
  const xTicks = niceTicks(lo, hi, 7);
  const yTicks = niceTicks(0, scales.yMax, 6);

  const upstreamPts = curvePointsInWindow(request.upstream, lo, hi);
  const downstreamPaths = request.downstream.map((d) => ({
    id: d.id,
    pts: curvePointsInWindow(d, lo, hi),
  }));

  const hovered: Interval | null =
    hoveredIndex !== null ? response.intervals[hoveredIndex] ?? null : null;
  const hoveredId = hovered?.responsible ?? null;

  return (
    <svg
      className="chart"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label="上下级保护曲线与非选择区间叠加图"
    >
      {/* 绘图区背景 */}
      <rect
        x={scales.padL}
        y={scales.padT}
        width={WIDTH - scales.padL - scales.padR}
        height={HEIGHT - scales.padT - scales.padB}
        fill="#f8fafc"
        stroke="#cbd5e1"
      />

      {/* 网格与刻度 */}
      {xTicks.map((t, i) => (
        <g key={`gx${i}`}>
          <line x1={sx(t)} y1={scales.padT} x2={sx(t)} y2={HEIGHT - scales.padB} stroke="#e2e8f0" />
          <text x={sx(t)} y={HEIGHT - scales.padB + 16} textAnchor="middle" className="tick">
            {t}
          </text>
        </g>
      ))}
      {yTicks.map((t, i) => (
        <g key={`gy${i}`}>
          <line x1={scales.padL} y1={sy(t)} x2={WIDTH - scales.padR} y2={sy(t)} stroke="#e2e8f0" />
          <text x={scales.padL - 8} y={sy(t) + 4} textAnchor="end" className="tick">
            {t}
          </text>
        </g>
      ))}

      {/* 轴标题 */}
      <text x={WIDTH / 2} y={HEIGHT - 6} textAnchor="middle" className="axis-title">
        电流 (μA)
      </text>
      <text
        x={16}
        y={HEIGHT / 2}
        textAnchor="middle"
        className="axis-title"
        transform={`rotate(-90 16 ${HEIGHT / 2})`}
      >
        动作时间 (μs)
      </text>

      {/* 非选择区间带（精确有理边界，仅像素定位用浮点） */}
      {response.intervals.map((iv, i) => {
        const x0 = rationalToNumber(iv.lo);
        const x1 = rationalToNumber(iv.hi);
        const active = hoveredIndex === i;
        const top = scales.padT;
        const bottom = HEIGHT - scales.padB;
        const isZero = x1 === x0;
        if (isZero) {
          // 零长度接触：用整条竖线 + 菱形显式保留，避免“采样漏掉”。
          return (
            <g
              key={`iv${i}`}
              onMouseEnter={() => onHoverIndex(i)}
              onMouseLeave={() => onHoverIndex(null)}
              className="band"
            >
              <line
                x1={sx(x0)}
                y1={top}
                x2={sx(x0)}
                y2={bottom}
                stroke={active ? '#b91c1c' : '#ef4444'}
                strokeWidth={active ? 4 : 2}
                strokeDasharray="3 3"
              />
              <polygon
                points={`${sx(x0)},${top + 4} ${sx(x0) + 6},${top + 12} ${sx(x0)},${top + 20} ${sx(x0) - 6},${top + 12}`}
                fill="#ef4444"
              />
            </g>
          );
        }
        return (
          <rect
            key={`iv${i}`}
            x={sx(x0)}
            y={top}
            width={Math.max(1, sx(x1) - sx(x0))}
            height={bottom - top}
            fill="#ef4444"
            opacity={active ? 0.42 : 0.18}
            stroke="#b91c1c"
            strokeWidth={active ? 2 : 1}
            onMouseEnter={() => onHoverIndex(i)}
            onMouseLeave={() => onHoverIndex(null)}
            className="band"
          />
        );
      })}

      {/* 下级曲线 */}
      {downstreamPaths.map(({ id, pts }) => {
        const emphasized = hoveredId === id;
        return (
          <polyline
            key={id}
            points={toPixelPoints(pts, scales)}
            fill="none"
            stroke={colorFor(id, request.upstream.id, downstreamIds)}
            strokeWidth={emphasized ? 4.5 : 2}
            opacity={hoveredId === null || emphasized ? 1 : 0.25}
          />
        );
      })}

      {/* 上级曲线 */}
      <polyline
        points={toPixelPoints(upstreamPts, scales)}
        fill="none"
        stroke={colorFor(request.upstream.id, request.upstream.id, downstreamIds)}
        strokeWidth={3.5}
      />

      {/* 精确上包络（黑色粗虚线置顶） */}
      <polyline
        points={toPixelPoints(envelope, scales)}
        fill="none"
        stroke="#111827"
        strokeWidth={2.5}
        strokeDasharray="7 5"
      />

      {/* 每区间差值最小点标记 */}
      {response.intervals.map((iv, i) => {
        const x = rationalToNumber(iv.min_current);
        const responsibleCurve =
          iv.responsible === request.upstream.id
            ? null
            : request.downstream.find((d) => d.id === iv.responsible) ?? null;
        if (!responsibleCurve) return null;
        const y = envelopeAt(envelope, x);
        return (
          <circle
            key={`min${i}`}
            cx={sx(x)}
            cy={sy(y)}
            r={hoveredIndex === i ? 7 : 5}
            fill="#fbbf24"
            stroke="#b45309"
            strokeWidth={2}
          />
        );
      })}

      {/* 图例 */}
      <g transform={`translate(${scales.padL + 8}, ${scales.padT + 8})`}>
        <rect x={-4} y={-6} width={150} height={20 * (downstreamIds.length + 3) + 6} fill="#ffffff" opacity={0.85} rx={4} />
        <LegendLine y={4} color={colorFor(request.upstream.id, request.upstream.id, downstreamIds)} width={3.5} label={`上级 ${request.upstream.id}`} />
        {downstreamIds.map((id, i) => (
          <LegendLine
            key={id}
            y={4 + (i + 1) * 20}
            color={colorFor(id, request.upstream.id, downstreamIds)}
            width={2}
            label={`下级 ${id}`}
            dimmed={hoveredId !== null && hoveredId !== id}
          />
        ))}
        <g transform={`translate(0, ${4 + (downstreamIds.length + 1) * 20})`}>
          <line x1={0} y1={0} x2={26} y2={0} stroke="#111827" strokeWidth={2.5} strokeDasharray="7 5" />
          <text x={32} y={4} className="legend-text">下级上包络</text>
        </g>
        <g transform={`translate(0, ${4 + (downstreamIds.length + 2) * 20})`}>
          <rect x={0} y={-8} width={26} height={12} fill="#ef4444" opacity={0.3} stroke="#b91c1c" />
          <text x={32} y={4} className="legend-text">非选择区间</text>
        </g>
      </g>
    </svg>
  );
}

function LegendLine({
  y, color, width, label, dimmed,
}: { y: number; color: string; width: number; label: string; dimmed?: boolean }) {
  return (
    <g transform={`translate(0, ${y})`} opacity={dimmed ? 0.3 : 1}>
      <line x1={0} y1={0} x2={26} y2={0} stroke={color} strokeWidth={width} />
      <text x={32} y={4} className="legend-text">{label}</text>
    </g>
  );
}

/** 在已构造的包络折线上取 x 处高度（用于标记差值最小点）。 */
function envelopeAt(envelope: Pt[], x: number): number {
  if (x <= envelope[0].x) return envelope[0].y;
  for (let i = 0; i < envelope.length - 1; i++) {
    const a = envelope[i];
    const b = envelope[i + 1];
    if (x >= a.x && x <= b.x) {
      const t = (x - a.x) / (b.x - a.x || 1);
      return a.y + t * (b.y - a.y);
    }
  }
  return envelope[envelope.length - 1].y;
}
