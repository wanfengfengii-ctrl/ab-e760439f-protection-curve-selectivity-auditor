import { parseToNumber } from '../rational';
import type { ReviewResult } from '../types';

export interface CurveInput {
  id: string;
  points: { current: number; time: number }[];
}

export interface ChartInput {
  window: { start: number; end: number };
  margin: number;
  upstream: CurveInput;
  downstream: CurveInput[];
}

interface Props {
  input: ChartInput;
  result: ReviewResult;
  highlight: number | null;
}

const WIDTH = 880;
const HEIGHT = 430;
const PAD = { left: 78, right: 24, top: 34, bottom: 52 };
const DOWNSTREAM_COLORS = ['#059669', '#d97706', '#7c3aed', '#dc2626', '#0891b2'];
const UPSTREAM_COLOR = '#1d4ed8';

function ticks(min: number, max: number, count: number): number[] {
  const out: number[] = [];
  for (let i = 0; i <= count; i += 1) {
    out.push(Math.round(min + ((max - min) * i) / count));
  }
  return out;
}

/** SVG 叠绘：上级/下级曲线、审查窗、不选择区间带与最小差值电流线。 */
export default function CurveChart({ input, result, highlight }: Props) {
  const curves = [input.upstream, ...input.downstream];
  const xMin = Math.min(
    input.window.start,
    ...curves.flatMap((c) => c.points.map((p) => p.current)),
  );
  const xMax = Math.max(
    input.window.end,
    ...curves.flatMap((c) => c.points.map((p) => p.current)),
  );
  const yMax = Math.max(...curves.flatMap((c) => c.points.map((p) => p.time)));

  const sx = (x: number) =>
    PAD.left + ((x - xMin) / (xMax - xMin)) * (WIDTH - PAD.left - PAD.right);
  const sy = (y: number) =>
    HEIGHT - PAD.bottom - (y / yMax) * (HEIGHT - PAD.top - PAD.bottom);

  const highlightedResponsible =
    highlight !== null ? result.intervals[highlight]?.responsible : undefined;

  const curveOpacity = (id: string) =>
    highlightedResponsible === undefined || highlightedResponsible === id ? 1 : 0.25;

  return (
    <svg
      data-testid="chart"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label="保护曲线叠绘图"
    >
      {/* 坐标轴 */}
      <line x1={PAD.left} y1={HEIGHT - PAD.bottom} x2={WIDTH - PAD.right} y2={HEIGHT - PAD.bottom} stroke="#475569" />
      <line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={HEIGHT - PAD.bottom} stroke="#475569" />
      {ticks(xMin, xMax, 6).map((t) => (
        <g key={`x-${t}`}>
          <line x1={sx(t)} y1={HEIGHT - PAD.bottom} x2={sx(t)} y2={HEIGHT - PAD.bottom + 5} stroke="#475569" />
          <text x={sx(t)} y={HEIGHT - PAD.bottom + 18} textAnchor="middle" fontSize="11" fill="#475569">
            {t}
          </text>
        </g>
      ))}
      {ticks(0, yMax, 5).map((t) => (
        <g key={`y-${t}`}>
          <line x1={PAD.left - 5} y1={sy(t)} x2={PAD.left} y2={sy(t)} stroke="#475569" />
          <text x={PAD.left - 8} y={sy(t) + 4} textAnchor="end" fontSize="11" fill="#475569">
            {t}
          </text>
        </g>
      ))}
      <text x={WIDTH / 2} y={HEIGHT - 8} textAnchor="middle" fontSize="13" fill="#334155">
        电流 I (µA)
      </text>
      <text x={16} y={HEIGHT / 2} textAnchor="middle" fontSize="13" fill="#334155" transform={`rotate(-90 16 ${HEIGHT / 2})`}>
        动作时间 t (µs)
      </text>

      {/* 审查窗背景 */}
      <rect
        data-testid="window-band"
        x={sx(input.window.start)}
        y={PAD.top}
        width={sx(input.window.end) - sx(input.window.start)}
        height={HEIGHT - PAD.top - PAD.bottom}
        fill="#64748b"
        opacity={0.08}
      />

      {/* 不选择区间带（零长度区间画成竖线，端点属于结果） */}
      {result.intervals.map((iv, i) => {
        const x1 = sx(parseToNumber(iv.start));
        const x2 = sx(parseToNumber(iv.end));
        const active = highlight === i;
        const common = {
          'data-testid': `violation-band-${i}`,
          'data-highlighted': active ? 'true' : 'false',
        };
        return x2 > x1 ? (
          <rect
            key={i}
            {...common}
            x={x1}
            y={PAD.top}
            width={x2 - x1}
            height={HEIGHT - PAD.top - PAD.bottom}
            fill="#ef4444"
            opacity={active ? 0.4 : 0.16}
            stroke={active ? '#b91c1c' : 'none'}
            strokeWidth={active ? 1.5 : 0}
          />
        ) : (
          <line
            key={i}
            {...common}
            x1={x1}
            y1={PAD.top}
            x2={x1}
            y2={HEIGHT - PAD.bottom}
            stroke="#ef4444"
            strokeWidth={active ? 5 : 3}
            opacity={active ? 0.9 : 0.6}
          />
        );
      })}

      {/* 最小差值电流虚线 */}
      {result.intervals.map((iv, i) => (
        <line
          key={`min-${i}`}
          data-testid={`min-current-${i}`}
          x1={sx(parseToNumber(iv.min_current))}
          y1={PAD.top}
          x2={sx(parseToNumber(iv.min_current))}
          y2={HEIGHT - PAD.bottom}
          stroke="#0f172a"
          strokeWidth={highlight === i ? 2 : 1}
          strokeDasharray="5 4"
          opacity={highlight === null || highlight === i ? 0.8 : 0.2}
        />
      ))}

      {/* 曲曲线叠绘 */}
      {curves.map((curve, idx) => {
        const isUpstream = idx === 0;
        const color = isUpstream
          ? UPSTREAM_COLOR
          : DOWNSTREAM_COLORS[(idx - 1) % DOWNSTREAM_COLORS.length];
        const emphasized = highlightedResponsible === curve.id;
        return (
          <polyline
            key={curve.id}
            data-testid={`curve-${curve.id}`}
            fill="none"
            stroke={color}
            strokeWidth={emphasized ? 4 : isUpstream ? 2.5 : 2}
            opacity={curveOpacity(curve.id)}
            points={curve.points.map((p) => `${sx(p.current)},${sy(p.time)}`).join(' ')}
          />
        );
      })}

      {/* 图例 */}
      {curves.map((curve, idx) => {
        const isUpstream = idx === 0;
        const color = isUpstream
          ? UPSTREAM_COLOR
          : DOWNSTREAM_COLORS[(idx - 1) % DOWNSTREAM_COLORS.length];
        const x = PAD.left + 12 + idx * 150;
        return (
          <g key={`legend-${curve.id}`} opacity={curveOpacity(curve.id)}>
            <line x1={x} y1={16} x2={x + 22} y2={16} stroke={color} strokeWidth={isUpstream ? 3 : 2.5} />
            <text x={x + 26} y={20} fontSize="12" fill="#334155">
              {curve.id}
              {isUpstream ? '（上级）' : ''}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
