/** 编辑器预填样例：上级与包络在窗内交叉，边界为分数 27700/7。 */

export const SAMPLE_PAYLOAD = JSON.stringify(
  {
    window: { start: 1000, end: 5000 },
    margin: 200,
    upstream: {
      id: 'QS-main',
      points: [
        { current: 500, time: 10000 },
        { current: 6000, time: 1000 },
      ],
    },
    downstream: [
      {
        id: 'QF-feeder-1',
        points: [
          { current: 500, time: 1000 },
          { current: 6000, time: 6000 },
        ],
      },
      {
        id: 'QF-feeder-2',
        points: [
          { current: 500, time: 2000 },
          { current: 6000, time: 1500 },
        ],
      },
    ],
  },
  null,
  2,
);
