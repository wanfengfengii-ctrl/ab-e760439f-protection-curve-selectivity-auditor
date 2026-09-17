import type { AnalysisResponse } from '../types';
import { rationalToLabel } from '../lib/rationals';

interface IntervalListProps {
  response: AnalysisResponse;
  hoveredIndex: number | null;
  onHoverIndex: (i: number | null) => void;
}

/**
 * 极大非选择区间列表。边界显示精确分数（附小数近似）。
 * 鼠标悬停某行时通知父组件，联动高亮图中对应区间与责任曲线。
 */
export function IntervalList({ response, hoveredIndex, onHoverIndex }: IntervalListProps) {
  if (response.safe) {
    return (
      <section className="panel result-panel" data-testid="result-panel">
        <h2>审查结论</h2>
        <p className="safe-banner" data-testid="safe-banner">
          ✅ 全审查窗 [{response.window.lo}, {response.window.hi}] μA
          内均满足选择性（上级时间 − 包络时间 &gt; 裕量），审查通过。
        </p>
      </section>
    );
  }

  return (
    <section className="panel result-panel" data-testid="result-panel">
      <h2>
        审查结论：检出 {response.intervals.length} 个极大非选择区间
      </h2>
      <p className="danger-hint">
        下列闭区间内“上级时间 − 下级上包络时间 ≤ 裕量”，上级可能不动作或同时动作，失去选择性。
      </p>
      <ul className="interval-list">
        {response.intervals.map((iv, i) => {
          const zero = iv.lo.num === iv.hi.num && iv.lo.den === iv.hi.den;
          return (
            <li
              key={i}
              className={`interval-row${hoveredIndex === i ? ' hovered' : ''}`}
              data-testid={`interval-row-${i}`}
              onMouseEnter={() => onHoverIndex(i)}
              onMouseLeave={() => onHoverIndex(null)}
            >
              <div className="interval-head">
                <span className="interval-index">#{i + 1}</span>
                <span className="interval-range">
                  [{rationalToLabel(iv.lo)}, {rationalToLabel(iv.hi)}] μA
                </span>
                {zero && <span className="zero-tag">零长度接触</span>}
              </div>
              <div className="interval-meta">
                责任下级：<strong>{iv.responsible}</strong>
                {' · '}
                最小差值：<strong>{rationalToLabel(iv.min_diff)}</strong> μs
                {' · '}
                出现于电流：<strong>{rationalToLabel(iv.min_current)}</strong> μA
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
