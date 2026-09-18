import { useCallback, useState } from 'react';
import { ApiRequestError, postReview } from './api';
import { SAMPLE_PAYLOAD } from './sample';
import type { ApiError, ReviewResult } from './types';
import CurveChart, { type ChartInput } from './components/CurveChart';
import IntervalList from './components/IntervalList';

export default function App() {
  const [text, setText] = useState(SAMPLE_PAYLOAD);
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [chartInput, setChartInput] = useState<ChartInput | null>(null);
  const [errors, setErrors] = useState<ApiError[] | null>(null);
  const [highlight, setHighlight] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = useCallback(async () => {
    setBusy(true);
    try {
      const res = await postReview(text);
      // 200 说明文本是合法 JSON，解析用于绘图
      setResult(res);
      setChartInput(JSON.parse(text) as ChartInput);
      setErrors(null);
      setHighlight(null);
    } catch (err) {
      const apiErrors =
        err instanceof ApiRequestError
          ? err.errors
          : [{ path: '', code: 'network', message: `请求失败：${String(err)}` }];
      // 整批拒绝：清除旧结果与旧图，绝不残留
      setErrors(apiErrors);
      setResult(null);
      setChartInput(null);
      setHighlight(null);
    } finally {
      setBusy(false);
    }
  }, [text]);

  const handleUpload = useCallback((file: File | undefined) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setText(String(reader.result ?? ''));
    reader.readAsText(file);
  }, []);

  return (
    <div className="page">
      <header>
        <h1>配电柜上下级保护曲线选择性审查</h1>
        <p className="hint">
          电流单位微安（µA）、动作时间微秒（µs）、裕量微秒（µs），均为整数；
          区间边界以约分有理数精确返回。
        </p>
      </header>

      <section className="editor">
        <div className="editor-toolbar">
          <label htmlFor="json-input">审查请求 JSON</label>
          <input
            data-testid="upload-input"
            type="file"
            accept=".json,application/json"
            onChange={(e) => handleUpload(e.target.files?.[0])}
          />
          <button
            data-testid="submit-button"
            disabled={busy}
            onClick={handleSubmit}
          >
            {busy ? '审查中…' : '提交审查'}
          </button>
        </div>
        <textarea
          id="json-input"
          data-testid="json-input"
          spellCheck={false}
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={22}
        />
      </section>

      {errors && (
        <section className="errors" data-testid="error-panel">
          <h2>请求被整批拒绝（{errors.length} 个错误）</h2>
          <ul>
            {errors.map((err, i) => (
              <li key={i} data-testid="error-item">
                <code>{err.path || '(请求体)'}</code>
                <span className="code">[{err.code}]</span> {err.message}
              </li>
            ))}
          </ul>
        </section>
      )}

      {result && (
        <section className="result">
          <div
            data-testid="verdict-banner"
            className={`verdict ${result.verdict}`}
          >
            {result.verdict === 'pass'
              ? '审查通过：整个闭合审查窗内满足选择性，无不选择区间。'
              : `审查未通过：发现 ${result.intervals.length} 个极大不选择区间。`}
          </div>
          {result.intervals.length > 0 && (
            <IntervalList
              intervals={result.intervals}
              highlight={highlight}
              onHighlight={setHighlight}
            />
          )}
          {chartInput && (
            <CurveChart input={chartInput} result={result} highlight={highlight} />
          )}
        </section>
      )}
    </div>
  );
}
