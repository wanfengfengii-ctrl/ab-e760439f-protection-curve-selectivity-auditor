import type { AnalysisRequest } from '../types';

/**
 * 内置示例：上级 U(x)=11-x（(1,10)->(7,4)），下级 D1 恒为 5us，
 * D2 恒为 1us；裕量 0。差值 d=6-x，故在 [6,7] 失去选择性，
 * 边界 6 为整数，便于首屏直观对照；上传/编辑可换成分数边界案例。
 */
export const DEFAULT_REQUEST: AnalysisRequest = {
  window: { lo: 1, hi: 7 },
  margin: 0,
  upstream: {
    id: 'U',
    points: [
      { current: 1, time: 10 },
      { current: 7, time: 4 },
    ],
  },
  downstream: [
    {
      id: 'D1',
      points: [
        { current: 1, time: 5 },
        { current: 7, time: 5 },
      ],
    },
    {
      id: 'D2',
      points: [
        { current: 1, time: 1 },
        { current: 7, time: 1 },
      ],
    },
  ],
};
