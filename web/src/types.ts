/** 与 API 契约对应的类型。边界值一律为约分有理数字符串："123" 或 "123/45"。 */

export interface IntervalResult {
  start: string;
  end: string;
  min_current: string;
  min_diff: string;
  responsible: string;
}

export interface ReviewResult {
  verdict: 'pass' | 'fail';
  intervals: IntervalResult[];
}

export interface ApiError {
  path: string;
  code: string;
  message: string;
}

export interface ApiErrorBody {
  errors: ApiError[];
}
