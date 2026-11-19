import { beforeEach, expect, it, vi } from 'vitest';

const mock = vi.hoisted(() => ({ request: vi.fn(), get: vi.fn(), post: vi.fn() }));
vi.mock('axios', () => ({ default: { create: () => mock, isAxiosError: () => false } }));
const ok = (data: unknown) => ({
  data: { code: 0, message: 'ok', data, request_id: 'request-test' },
});
beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
});

it('sends normalized registration fields and never signs in automatically', async () => {
  const { api } = await import('../src/api');
  mock.request.mockResolvedValueOnce(ok({ id: 12, status: 'active' }));
  await api.register({
    email: ' USER@EXAMPLE.COM ',
    password: 'safe-long-password',
    verification_code: '001234',
    real_name: ' 林知远 ',
  });
  expect(mock.request).toHaveBeenCalledOnce();
  expect(mock.request.mock.calls[0]?.[0]).toMatchObject({
    method: 'POST',
    url: '/auth/register',
    data: { email: 'user@example.com', verification_code: '001234', real_name: '林知远' },
  });
  expect(mock.post).not.toHaveBeenCalled();
});
it('refuses role injection before sending any request', async () => {
  const { api } = await import('../src/api');
  expect(() =>
    api.register({
      email: 'user@example.com',
      password: 'safe-long-password',
      verification_code: '001234',
      real_name: '林知远',
      role: 'platform_admin',
    }),
  ).toThrow();
  expect(mock.request).not.toHaveBeenCalled();
});
it('requires null data for accepted code and reset responses', async () => {
  const { api } = await import('../src/api');
  mock.request.mockResolvedValueOnce(ok({ delivered: true }));
  await expect(
    api.sendVerificationCode({ email: 'user@example.com', purpose: 'register' }),
  ).rejects.toMatchObject({ code: 50201 });
  mock.request.mockResolvedValueOnce(ok(null));
  await expect(
    api.resetPassword({
      email: 'user@example.com',
      verification_code: '001234',
      new_password: 'safe-long-password',
    }),
  ).resolves.toBeNull();
});
