import type { AnalysisRequest, AnalysisResponse, ApiError } from '../types';

export interface AnalyzeOk {
  ok: true;
  data: AnalysisResponse;
}

export interface AnalyzeErr {
  ok: false;
  errors: ApiError[];
}

export type AnalyzeResult = AnalyzeOk | AnalyzeErr;

/**
 * 调用后端分析。HTTP 层不抛错：校验失败（422）、坏 JSON（400）都归一化为
 * {ok:false, errors}，由 UI 整批显示并确保不残留旧图。
 */
export async function analyze(
  payload: AnalysisRequest,
  signal?: AbortSignal,
): Promise<AnalyzeResult> {
  let res: Response;
  try {
    res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    });
  } catch {
    return {
      ok: false,
      errors: [{ path: [], message: '无法连接分析服务（API 未启动？）' }],
    };
  }

  let body: unknown;
  try {
    body = await res.json();
  } catch {
    return {
      ok: false,
      errors: [{ path: [], message: `服务返回了非 JSON 响应（HTTP ${res.status}）` }],
    };
  }

  if (res.status === 200) {
    return { ok: true, data: body as AnalysisResponse };
  }

  const errors =
    typeof body === 'object' && body !== null && Array.isArray((body as any).errors)
      ? ((body as { errors: ApiError[] }).errors)
      : [{ path: [] as (string | number)[], message: `请求失败（HTTP ${res.status}）` }];
  return { ok: false, errors };
}

/** 把错误路径片段渲染成人类可读的 JSON 指针。 */
export function formatPath(path: (string | number)[]): string {
  if (path.length === 0) return '(根)';
  return '/' + path.map((p) => String(p)).join('/');
}
