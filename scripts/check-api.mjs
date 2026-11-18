import assert from 'node:assert/strict';

// Real HTTP checks. Credentials are explicit environment inputs, never demo defaults.
const base = new URL(process.env.API_BASE_URL || 'http://127.0.0.1:8000/api/v1/');
let checks = 0;

async function request(path, options = {}) {
  const response = await fetch(new URL(path, base), {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
    signal: AbortSignal.timeout(15_000),
  });
  const body = await response.json();
  assert(body && typeof body === 'object' && !Array.isArray(body));
  assert(Number.isInteger(body.code));
  assert.equal(typeof body.message, 'string');
  assert.equal(typeof body.request_id, 'string');
  assert(body.request_id.length > 0);
  assert('data' in body);
  checks += 1;
  return { response, body };
}

const anonymous = await request('me');
assert.equal(anonymous.response.status, 401);
assert.equal(anonymous.body.data, null);

for (const body of [
  '[]',
  '{"login_type":"email","email":true,"password":"not-a-credential"}',
  '{"login_type":"email","email":"sample@example.invalid","password":12}',
  '{"login_type":"email","email":"sample@example.invalid","password":"x","role":"platform_admin"}',
  '{"login_type":"email","login_type":"email","email":"sample@example.invalid","password":"x"}',
  '{"login_type":"email","email":"sample@example.invalid","password":1e999}',
]) {
  const result = await request('auth/login', { method: 'POST', body });
  assert.equal(result.response.status, 400);
  assert.equal(result.body.code, 40001);
  assert.equal(result.body.data, null);
}

const publicEvents = await request('public/competitions');
assert.equal(publicEvents.response.status, 200);
assert(Array.isArray(publicEvents.body.data.items));
assert(Number.isInteger(publicEvents.body.data.total));

if (process.env.TEST_USER_EMAIL && process.env.TEST_USER_PASSWORD) {
  const login = await request('auth/login', {
    method: 'POST',
    body: JSON.stringify({
      login_type: 'email',
      email: process.env.TEST_USER_EMAIL,
      password: process.env.TEST_USER_PASSWORD,
    }),
  });
  assert.equal(login.response.status, 200);
  assert.equal(typeof login.body.data.access, 'string');
  assert.equal(login.body.data.expires_in, 1800);
  const cookies = login.response.headers.getSetCookie();
  assert(cookies.some((cookie) => /httponly/i.test(cookie)));
  assert(cookies.some((cookie) => /samesite=strict/i.test(cookie)));
  const me = await request('me', {
    headers: { Authorization: `Bearer ${login.body.data.access}` },
  });
  assert.equal(me.response.status, 200);
  assert(Array.isArray(me.body.data.grants));
  assert.equal(me.body.data.user.email, process.env.TEST_USER_EMAIL);
  const invalid = await request('me', {
    headers: { Authorization: `Bearer ${login.body.data.access}invalid` },
  });
  assert.equal(invalid.response.status, 401);
  assert.equal(invalid.body.data, null);
} else {
  process.stdout.write('Authenticated checks skipped: provide TEST_USER_EMAIL and TEST_USER_PASSWORD.\n');
}

process.stdout.write(`PASS: ${checks} real HTTP contract and authentication checks.\n`);
