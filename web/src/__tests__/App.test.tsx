import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../App';

const FAIL_RESULT = {
  verdict: 'fail',
  intervals: [
    {
      start: '27700/7',
      end: '5000',
      min_current: '5000',
      min_diff: '-27000/11',
      responsible: 'QF-feeder-1',
    },
  ],
};

const PASS_RESULT = { verdict: 'pass', intervals: [] };

const REJECT_ERRORS = {
  errors: [
    { path: 'downstream[0].id', code: 'duplicate_id', message: "标识 'QS-main' 重复" },
    { path: 'downstream[1].points', code: 'too_few_points', message: '每条曲线至少需要两个折点' },
  ],
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function mockFetchSequence(...steps: { status: number; body: unknown }[]) {
  const fn = vi.fn();
  for (const step of steps) {
    fn.mockResolvedValueOnce(jsonResponse(step.status, step.body));
  }
  vi.stubGlobal('fetch', fn);
  return fn;
}

function submit() {
  fireEvent.click(screen.getByTestId('submit-button'));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('App', () => {
  it('合法结果显示区间列表、精确边界与 SVG 叠绘图', async () => {
    mockFetchSequence({ status: 200, body: FAIL_RESULT });
    render(<App />);
    submit();
    const banner = await screen.findByTestId('verdict-banner');
    expect(banner).toHaveTextContent('审查未通过');
    expect(banner).toHaveTextContent('1 个极大不选择区间');
    const row = screen.getByTestId('interval-row');
    expect(row).toHaveTextContent('27700/7');
    expect(row).toHaveTextContent('-27000/11');
    expect(row).toHaveTextContent('QF-feeder-1');
    expect(screen.getByTestId('chart')).toBeInTheDocument();
    expect(screen.getByTestId('violation-band-0')).toBeInTheDocument();
  });

  it('悬停区间行时高亮对应区间带与责任曲线', async () => {
    mockFetchSequence({ status: 200, body: FAIL_RESULT });
    render(<App />);
    submit();
    const row = await screen.findByTestId('interval-row');
    const band = screen.getByTestId('violation-band-0');
    expect(band).toHaveAttribute('data-highlighted', 'false');
    fireEvent.mouseEnter(row);
    expect(band).toHaveAttribute('data-highlighted', 'true');
    const curve = screen.getByTestId('curve-QF-feeder-1');
    expect(curve).toHaveAttribute('stroke-width', '4');
    fireEvent.mouseLeave(row);
    expect(band).toHaveAttribute('data-highlighted', 'false');
  });

  it('整批拒绝时展示全部错误且清除旧图，不得残留', async () => {
    mockFetchSequence(
      { status: 200, body: FAIL_RESULT },
      { status: 422, body: REJECT_ERRORS },
    );
    render(<App />);
    submit();
    await screen.findByTestId('verdict-banner');
    expect(screen.getByTestId('chart')).toBeInTheDocument();
    // 第二次提交被整批拒绝
    submit();
    await screen.findByTestId('error-panel');
    expect(screen.queryByTestId('chart')).not.toBeInTheDocument();
    expect(screen.queryByTestId('verdict-banner')).not.toBeInTheDocument();
    const items = screen.getAllByTestId('error-item');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('downstream[0].id');
    expect(items[0]).toHaveTextContent('duplicate_id');
    expect(items[1]).toHaveTextContent('too_few_points');
  });

  it('全窗安全时明确显示通过', async () => {
    mockFetchSequence({ status: 200, body: PASS_RESULT });
    render(<App />);
    submit();
    const banner = await screen.findByTestId('verdict-banner');
    expect(banner).toHaveTextContent('审查通过');
    expect(screen.queryByTestId('interval-row')).not.toBeInTheDocument();
  });

  it('网络失败也清除旧图并提示', async () => {
    const fn = vi.fn();
    fn.mockResolvedValueOnce(jsonResponse(200, FAIL_RESULT));
    fn.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', fn);
    render(<App />);
    submit();
    await screen.findByTestId('verdict-banner');
    submit();
    await screen.findByTestId('error-panel');
    expect(screen.queryByTestId('chart')).not.toBeInTheDocument();
    expect(screen.getByTestId('error-item')).toHaveTextContent('请求失败');
  });

  it('文件上传填入编辑器', async () => {
    render(<App />);
    const file = new File(['{"window":{}}'], 'case.json', { type: 'application/json' });
    const input = screen.getByTestId('upload-input') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => {
      expect(screen.getByTestId('json-input')).toHaveValue('{"window":{}}');
    });
  });
});
