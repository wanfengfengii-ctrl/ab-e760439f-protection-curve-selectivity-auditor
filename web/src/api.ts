import type { ApiError, ApiErrorBody, ReviewResult } from './types';

/** 整批拒绝（422）或传输失败时抛出，携带后端返回的全部错误。 */
export class ApiRequestError extends Error {
  constructor(public readonly errors: ApiError[]) {
    super('请求被整批拒绝');
    this.name = 'ApiRequestError';
  }
}

export async function postReview(bodyText: string): Promise<ReviewResult> {
  const resp = await fetch('/api/review', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: bodyText,
  });
  const data = (await resp.json()) as ReviewResult & ApiErrorBody;
  if (resp.ok) {
    return data;
  }
  throw new ApiRequestError(
    Array.isArray(data.errors) && data.errors.length > 0
      ? data.errors
      : [{ path: '', code: 'unknown', message: `未知错误（HTTP ${resp.status}）` }],
  );
}
