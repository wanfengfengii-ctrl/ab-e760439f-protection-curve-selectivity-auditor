// 与后端契约一一对应的领域类型。所有电流/时间/裕量都是整数计数。

export interface Point {
  current: number; // 微安 uA，正整数
  time: number; // 微秒 us，正整数
}

export interface Protector {
  id: string;
  points: Point[];
}

export interface ReviewWindow {
  lo: number;
  hi: number;
}

export interface AnalysisRequest {
  window: ReviewWindow;
  upstream: Protector;
  downstream: Protector[];
  margin: number; // 微秒 us，非负整数
}

export interface Rational {
  num: number;
  den: number; // 恒正、已约分
}

export interface Interval {
  lo: Rational;
  hi: Rational;
  min_diff: Rational;
  min_current: Rational;
  responsible: string;
}

export interface EnvelopeSegment {
  lo: Rational;
  hi: Rational;
  lo_time: Rational;
  hi_time: Rational;
  responsible: string;
}

export interface AnalysisResponse {
  safe: boolean;
  intervals: Interval[];
  envelope: EnvelopeSegment[];
  window: ReviewWindow;
}

export interface ApiError {
  path: (string | number)[];
  message: string;
}
