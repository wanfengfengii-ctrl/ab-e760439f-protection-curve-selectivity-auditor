import { useMemo, useState } from 'react';
import type { AnalysisRequest, AnalysisResponse, ApiError } from './types';
import { analyze, formatPath } from './lib/api';
import { DEFAULT_REQUEST } from './lib/sample';
import { JsonEditor } from './components/JsonEditor';
import { Chart } from './components/Chart';
import { IntervalList } from './components/IntervalList';

interface Submitted {
  request: AnalysisRequest;
  response: AnalysisResponse;
}

export default function App() {
  const [text, setText] = useState(() => JSON.stringify(DEFAULT_REQUEST, null, 2));
  const [submitted, setSubmitted] = useState<Submitted | null>(null);
  const [errors, setErrors] = useState<ApiError[]>([]);
  const [localError, setLocalError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const requestSummary = useMemo(() => {
    if (!submitted) return null;
    const { request } = submitted;
    return {
      window: `[${request.window.lo}, ${request.window.hi}] μA`,
      margin: `${request.margin} μs`,
      upstream: request.upstream.id,
      downstream: request.downstream.map((d) => d.id).join(', '),
    };
  }, [submitted]);

  async function handleSubmit() {
    setLoading(true);
    setLocalError(null);
    setErrors([]);

    let parsed: AnalysisRequest;
    try {
      parsed = JSON.parse(text) as AnalysisRequest;
    } catch (e) {
      // 本地都不是合法 JSON：不发请求，并清空任何旧图。
      setSubmitted(null);
      setLocalError(`JSON 解析失败：${(e as Error).message}`);
      setLoading(false);
      return;
    }

    const result = await analyze(parsed);
    if (result.ok) {
      // 只有合法结果才画图；旧的非法状态被整体替换。
      setSubmitted({ request: parsed, response: result.data });
      setErrors([]);
      setHoveredIndex(null);
    } else {
      // 整批拒绝：清空旧图，绝不残留。
      setSubmitted(null);
      setErrors(result.errors);
    }
    setLoading(false);
  }

  function handleReset() {
    setText(JSON.stringify(DEFAULT_REQUEST, null, 2));
    setSubmitted(null);
    setErrors([]);
    setLocalError(null);
    setHoveredIndex(null);
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>配电柜上下级保护曲线 · 选择性精确审查</h1>
        <p className="subtitle">
          整数微安 / 微秒输入，边界以约分有理数精确给出；折点间按电流线性插值，
          下级取逐段最大上包络。
        </p>
      </header>

      <div className="layout">
        <div className="left">
          <JsonEditor value={text} onChange={setText} />
          <div className="actions">
            <button type="button" className="btn primary" onClick={() => void handleSubmit()} disabled={loading}>
              {loading ? '审查中…' : '提交审查'}
            </button>
            <button type="button" className="btn ghost" onClick={handleReset} disabled={loading}>
              重置为示例
            </button>
          </div>

          {localError && (
            <div className="error-panel" data-testid="local-error">
              <strong>无法提交：</strong>
              {localError}
            </div>
          )}

          {errors.length > 0 && (
            <div className="error-panel" data-testid="error-panel">
              <strong>整批拒绝：共 {errors.length} 处错误（已清空旧图，未进行任何分析）</strong>
              <ul className="error-list">
                {errors.map((e, i) => (
                  <li key={i}>
                    <code className="error-path">{formatPath(e.path)}</code>
                    <span className="error-msg">{e.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="right">
          {submitted ? (
            <>
              {requestSummary && (
                <section className="panel summary" data-testid="summary">
                  <span>审查窗：<strong>{requestSummary.window}</strong></span>
                  <span>裕量：<strong>{requestSummary.margin}</strong></span>
                  <span>上级：<strong>{requestSummary.upstream}</strong></span>
                  <span>下级：<strong>{requestSummary.downstream}</strong></span>
                </section>
              )}
              <section className="panel chart-panel" data-testid="chart-panel">
                <Chart
                  request={submitted.request}
                  response={submitted.response}
                  hoveredIndex={hoveredIndex}
                  onHoverIndex={setHoveredIndex}
                />
              </section>
              <IntervalList
                response={submitted.response}
                hoveredIndex={hoveredIndex}
                onHoverIndex={setHoveredIndex}
              />
            </>
          ) : (
            <section className="panel placeholder" data-testid="placeholder">
              <p>编辑或上传 JSON 后点击“提交审查”。</p>
              <p className="muted">
                约定：window 为闭合审查窗（正整数 μA）；margin 为非负整数 μs；
                upstream 为一个上级、downstream 至少两个下级；每条曲线 ≥2 个折点，
                电流为严格递增正整数（μA）、时间为正整数（μs），且首尾折点必须覆盖审查窗。
              </p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
