import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiRequestError, postReview } from '../api';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('postReview', () => {
  it('200 时返回审查结果', async () => {
    const body = {
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
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, body));
    vi.stubGlobal('fetch', fetchMock);
    const result = await postReview('{"window":{}}');
    expect(result).toEqual(body);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/review',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('422 时抛出携带全部错误的 ApiRequestError', async () => {
    const errors = [
      { path: 'margin', code: 'negative', message: '裕量必须是非负整数（>= 0）' },
      { path: 'downstream[0].id', code: 'duplicate_id', message: "标识 'dup' 重复" },
    ];
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(422, { errors })));
    const err = await postReview('{}').catch((e) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect((err as ApiRequestError).errors).toEqual(errors);
  });

  it('网络异常时按异常向上抛', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(postReview('{}')).rejects.toThrow('Failed to fetch');
  });
});
