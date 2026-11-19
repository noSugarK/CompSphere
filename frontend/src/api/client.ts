import axios from 'axios';
import { z } from 'zod';
import { csrfSchema, envelopeSchema, errorSchema, tokenSchema } from './schemas';

const transport = axios.create({ baseURL: '/api/v1', withCredentials: true, timeout: 15000 });
let access = '';
let csrf = '';
let generation = 0;
let refreshPromise: Promise<void> | undefined;
let refreshEpoch = -1;
let onExpired = () => {};
export function setSessionToken(token: string) {
  access = token;
}
export function clearSessionToken() {
  access = '';
  csrf = '';
  generation += 1;
}
export function onSessionExpired(callback: () => void) {
  onExpired = callback;
}
export class ApiError extends Error {
  constructor(
    public code: number,
    public requestId = '',
    public fields: Record<string, string[]> = {},
    public retryAfterSeconds?: number,
  ) {
    super(`API ${code}`);
  }
}
export function parseRetryAfter(value: unknown, now = Date.now()): number | undefined {
  if (typeof value !== 'string' || !value.trim()) return;
  const trimmed = value.trim();
  if (/^[0-9]+$/.test(trimmed)) {
    const seconds = Number(trimmed);
    return Number.isSafeInteger(seconds) ? seconds : undefined;
  }
  // HTTP-date is accepted only with an explicit GMT timezone, never a browser-local date.
  if (!/^[A-Z][a-z]{2}, [0-9]{2} [A-Z][a-z]{2} [0-9]{4} [0-9:]{8} GMT$/.test(trimmed)) return;
  const target = Date.parse(trimmed);
  if (!Number.isFinite(target)) return;
  return Math.max(0, Math.ceil((target - now) / 1000));
}
export function decode<T extends z.ZodTypeAny>(input: unknown, schema: T): z.infer<T> {
  const parsed = envelopeSchema(z.unknown()).safeParse(input);
  if (!parsed.success) throw new ApiError(50201);
  const data = schema.safeParse(parsed.data.data);
  if (!data.success) throw new ApiError(50201);
  return data.data;
}
export async function refreshSession() {
  if (refreshPromise && refreshEpoch === generation) return refreshPromise;
  const epoch = generation;
  refreshEpoch = epoch;
  const pending = (async () => {
    try {
      if (!csrf) {
        const nextCsrf = decode(
          (await transport.get<unknown>('/auth/csrf')).data,
          csrfSchema,
        ).csrf_token;
        if (epoch !== generation) throw new ApiError(40101);
        csrf = nextCsrf;
      }
      const response = await transport.post<unknown>(
        '/auth/refresh',
        {},
        { headers: { 'X-CSRFToken': csrf } },
      );
      const token = decode(response.data, tokenSchema);
      if (epoch !== generation) throw new ApiError(40101);
      access = token.access;
    } catch (error) {
      if (epoch === generation) {
        clearSessionToken();
        onExpired();
      }
      if (axios.isAxiosError(error) && error.response?.status === 401) throw new ApiError(40101);
      throw error instanceof ApiError ? error : new ApiError(50301);
    }
  })().finally(() => {
    if (refreshPromise === pending) refreshPromise = undefined;
  });
  refreshPromise = pending;
  return refreshPromise;
}
export async function request<T extends z.ZodTypeAny>(
  method: string,
  url: string,
  schema: T,
  data?: unknown,
  headers?: Record<string, string>,
  retry = true,
): Promise<z.infer<T>> {
  const epoch = generation;
  try {
    const response = await transport.request<unknown>({
      method,
      url,
      data,
      headers: { ...(access ? { Authorization: `Bearer ${access}` } : {}), ...headers },
    });
    if (epoch !== generation) throw new ApiError(40101);
    return decode(response.data, schema);
  } catch (error) {
    // A late 401 must never replay an old actor's mutation under a new session.
    if (epoch !== generation) throw new ApiError(40101);
    if (error instanceof ApiError) throw error;
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 401 && retry && !url.startsWith('/auth/')) {
        await refreshSession();
        if (epoch !== generation) throw new ApiError(40101);
        return request(method, url, schema, data, headers, false);
      }
      const failure = errorSchema.safeParse(error.response?.data);
      if (failure.success) {
        if (failure.data.code === 40101) {
          clearSessionToken();
          onExpired();
        }
        throw new ApiError(
          failure.data.code,
          failure.data.request_id,
          failure.data.errors,
          error.response?.status === 429
            ? parseRetryAfter(error.response.headers?.['retry-after'])
            : undefined,
        );
      }
    }
    throw new ApiError(50301);
  }
}
export async function logoutSession() {
  const epoch = generation;
  try {
    if (!csrf) {
      const nextCsrf = decode(
        (await transport.get<unknown>('/auth/csrf')).data,
        csrfSchema,
      ).csrf_token;
      if (epoch !== generation) throw new ApiError(40101);
      csrf = nextCsrf;
    }
    if (epoch !== generation) throw new ApiError(40101);
    await request('POST', '/auth/logout', z.null(), {}, { 'X-CSRFToken': csrf });
  } finally {
    if (epoch === generation) {
      clearSessionToken();
      onExpired();
    }
  }
}
