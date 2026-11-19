import { beforeEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';

const mock = vi.hoisted(() => ({ request: vi.fn(), get: vi.fn(), post: vi.fn() }));
vi.mock('axios', () => ({
  default: {
    create: () => mock,
    isAxiosError: (error: unknown) =>
      !!error && typeof error === 'object' && 'isAxiosError' in error,
  },
}));
const ok = (data: unknown) => ({
  data: { code: 0, message: 'ok', data, request_id: 'request-test' },
});
const unauthorized = () => ({
  isAxiosError: true,
  response: {
    status: 401,
    data: { code: 40101, message: 'expired', data: null, request_id: 'request-test' },
  },
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}
beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  mock.get.mockResolvedValue(ok({ csrf_token: 'csrf' }));
});
describe('session isolation', () => {
  it('carries only validated real Retry-After feedback from a 429 response', async () => {
    const client = await import('../src/api/client');
    mock.request.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 429,
        headers: { 'retry-after': '72' },
        data: { code: 42901, message: 'rate limited', data: null, request_id: 'request-test' },
      },
    });
    await expect(
      client.request('POST', '/auth/verify-code/send', z.null(), {}),
    ).rejects.toMatchObject({ code: 42901, retryAfterSeconds: 72 });
    expect(mock.post).not.toHaveBeenCalled();
  });
  it('keeps failed verification separate from an expired session', async () => {
    const client = await import('../src/api/client');
    const expired = vi.fn();
    client.onSessionExpired(expired);
    mock.request.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 401,
        data: { code: 40102, message: 'invalid code', data: null, request_id: 'request-test' },
      },
    });
    await expect(
      client.request('POST', '/auth/password/reset', z.null(), {}),
    ).rejects.toMatchObject({ code: 40102 });
    expect(expired).not.toHaveBeenCalled();
    expect(mock.post).not.toHaveBeenCalled();
  });
  it('rejects malformed Retry-After and converts explicit HTTP dates', async () => {
    const { parseRetryAfter } = await import('../src/api/client');
    expect(parseRetryAfter('30')).toBe(30);
    expect(
      parseRetryAfter('Wed, 18 Nov 2026 10:01:00 GMT', Date.parse('2026-11-18T10:00:00Z')),
    ).toBe(60);
    expect(parseRetryAfter('-1')).toBeUndefined();
    expect(parseRetryAfter('tomorrow')).toBeUndefined();
    expect(parseRetryAfter(30)).toBeUndefined();
    expect(parseRetryAfter('Infinity')).toBeUndefined();
  });
  it('shares one refresh across simultaneous 401 responses', async () => {
    const client = await import('../src/api/client');
    const token = deferred<ReturnType<typeof ok>>();
    mock.post.mockReturnValue(token.promise);
    mock.request
      .mockRejectedValueOnce(unauthorized())
      .mockRejectedValueOnce(unauthorized())
      .mockResolvedValue(ok('done'));
    const a = client.request('GET', '/one', z.string());
    const b = client.request('GET', '/two', z.string());
    await vi.waitFor(() => expect(mock.post).toHaveBeenCalledTimes(1));
    token.resolve(ok({ access: 'new-token', expires_in: 1800 }));
    expect(await Promise.all([a, b])).toEqual(['done', 'done']);
    expect(mock.post).toHaveBeenCalledTimes(1);
  });
  it('never refreshes or replays actor A’s late mutation under actor B', async () => {
    const client = await import('../src/api/client');
    const old = deferred<ReturnType<typeof ok>>();
    mock.request.mockReturnValueOnce(old.promise);
    client.setSessionToken('actor-a');
    const pending = client
      .request('PATCH', '/registrations/1', z.null(), { version: 1 })
      .catch((e: unknown) => e);
    client.clearSessionToken();
    client.setSessionToken('actor-b');
    old.reject(unauthorized());
    expect(await pending).toBeInstanceOf(client.ApiError);
    expect(mock.post).not.toHaveBeenCalled();
    expect(mock.request).toHaveBeenCalledTimes(1);
  });
  it('does not replay an old mutation if another refresh waiter changes account first', async () => {
    const client = await import('../src/api/client');
    const token = deferred<ReturnType<typeof ok>>();
    mock.post.mockReturnValueOnce(token.promise);
    client.setSessionToken('actor-a');
    const switchActor = client.refreshSession().then(() => {
      client.clearSessionToken();
      client.setSessionToken('actor-b');
    });
    await vi.waitFor(() => expect(mock.post).toHaveBeenCalledOnce());
    mock.request.mockRejectedValueOnce(unauthorized()).mockResolvedValue(ok(null));
    const pending = client
      .request('PATCH', '/registrations/1', z.null(), { version: 1 })
      .catch((e: unknown) => e);
    await vi.waitFor(() => expect(mock.request).toHaveBeenCalledOnce());
    token.resolve(ok({ access: 'refreshed-actor-a', expires_in: 1800 }));
    await switchActor;
    expect(await pending).toMatchObject({ code: 40101 });
    expect(mock.request).toHaveBeenCalledOnce();
    expect(mock.post).toHaveBeenCalledOnce();
  });
  it('does not let an obsolete refresh failure clear a new login', async () => {
    const client = await import('../src/api/client');
    const expired = vi.fn();
    client.onSessionExpired(expired);
    const old = deferred<ReturnType<typeof ok>>();
    mock.post.mockReturnValueOnce(old.promise);
    const pending = client.refreshSession().catch((e: unknown) => e);
    await vi.waitFor(() => expect(mock.post).toHaveBeenCalledOnce());
    client.clearSessionToken();
    client.setSessionToken('actor-b');
    old.reject(unauthorized());
    await pending;
    mock.request.mockResolvedValueOnce(ok('safe'));
    await client.request('GET', '/me', z.string());
    expect(expired).not.toHaveBeenCalled();
    expect(mock.request.mock.lastCall?.[0].headers.Authorization).toBe('Bearer actor-b');
  });
  it('clears private session on logout failure', async () => {
    const client = await import('../src/api/client');
    const expired = vi.fn();
    client.onSessionExpired(expired);
    client.setSessionToken('old');
    mock.request.mockRejectedValueOnce(new Error('network unavailable'));
    await expect(client.logoutSession()).rejects.toBeInstanceOf(client.ApiError);
    expect(expired).toHaveBeenCalledOnce();
    mock.request.mockResolvedValueOnce(ok(null));
    await client.request('GET', '/public', z.null());
    expect(mock.request.mock.lastCall?.[0].headers.Authorization).toBeUndefined();
  });
  it('never accepts malformed success data', async () => {
    const client = await import('../src/api/client');
    mock.request.mockResolvedValueOnce(ok({ id: '1' }));
    await expect(
      client.request('GET', '/resource', z.object({ id: z.number() }).strict()),
    ).rejects.toMatchObject({ code: 50201 });
  });
});
