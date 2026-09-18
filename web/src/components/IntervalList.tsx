import type { IntervalResult } from '../types';

interface Props {
  intervals: IntervalResult[];
  highlight: number | null;
  onHighlight: (index: number | null) => void;
}

/** 不选择区间列表：悬停行时高亮图表中对应区间与责任曲线。 */
export default function IntervalList({ intervals, highlight, onHighlight }: Props) {
  return (
    <table className="interval-table">
      <thead>
        <tr>
          <th>#</th>
          <th>区间起点 (µA)</th>
          <th>区间终点 (µA)</th>
          <th>最小差值电流 (µA)</th>
          <th>最小差值 (µs)</th>
          <th>责任下级</th>
        </tr>
      </thead>
      <tbody>
        {intervals.map((iv, i) => (
          <tr
            key={i}
            data-testid="interval-row"
            className={highlight === i ? 'highlighted' : ''}
            onMouseEnter={() => onHighlight(i)}
            onMouseLeave={() => onHighlight(null)}
          >
            <td>{i + 1}</td>
            <td className="num">{iv.start}</td>
            <td className="num">{iv.end}</td>
            <td className="num">{iv.min_current}</td>
            <td className="num">{iv.min_diff}</td>
            <td>{iv.responsible}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
