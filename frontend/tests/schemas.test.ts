import { describe, expect, it } from 'vitest';
import {
  aiOutputSchema,
  csrfSchema,
  envelopeSchema,
  idSchema,
  loginSchema,
  meSchema,
  pageSchema,
  seasonSchema,
} from '../src/api/schemas';
import {
  mayCreateCompetition,
  mayEnter,
  mayRenderPrivate,
  mayViewCompetitionRegistry,
} from '../src/utils/permissions';

const actor = meSchema.parse({
  user: { id: 1, username: 'test-user', email: null, must_change_password: false },
  profile: null,
  grants: [
    {
      role: 'participant',
      scope_type: 'global',
      scope_id: null,
      permissions: ['registration:create'],
    },
  ],
  locale: 'zh-CN',
  theme: 'system',
});
describe('untrusted JSON boundaries', () => {
  it.each([true, false, '1', 0, -1, 1.1, Number.MAX_SAFE_INTEGER + 1, null])(
    'rejects invalid ID %s',
    (id) => expect(idSchema.safeParse(id).success).toBe(false),
  );
  it('rejects missing response fields and extra top-level fields', () => {
    const schema = envelopeSchema(csrfSchema);
    expect(
      schema.safeParse({ code: 0, message: 'ok', data: { csrf_token: 'token' } }).success,
    ).toBe(false);
    expect(
      schema.safeParse({
        code: 0,
        message: 'ok',
        data: { csrf_token: 'token' },
        request_id: 'r',
        actor: 'admin',
      }).success,
    ).toBe(false);
  });
  it('rejects oversized pagination and invalid dates', () => {
    expect(
      pageSchema(idSchema).safeParse({ items: [1], page: 1, page_size: 101, total: 1 }).success,
    ).toBe(false);
    expect(
      seasonSchema.safeParse({
        id: 1,
        name: 'season',
        start_date: '2026-02-30',
        end_date: 'tomorrow',
        status: 'active',
      }).success,
    ).toBe(false);
  });
  it('rejects forged actor fields and mixed login branches', () => {
    expect(
      loginSchema.safeParse({
        login_type: 'email',
        email: 'test@example.com',
        password: 'password',
        role: 'platform_admin',
      }).success,
    ).toBe(false);
    expect(
      loginSchema.safeParse({
        login_type: 'email',
        email: 'test@example.com',
        password: 'password',
        document_number: 'secret',
      }).success,
    ).toBe(false);
  });
  it('rejects unknown AI tools, extra args and authority injection', () => {
    for (const output of [
      { kind: 'tool_proposal', tool: 'sql.execute', arguments: { sql: 'SELECT 1' } },
      {
        kind: 'tool_proposal',
        tool: 'registration.open',
        arguments: { registration_id: 1, actor: 2 },
      },
      {
        kind: 'tool_proposal',
        tool: 'registration.update_draft',
        arguments: { registration_id: 1, version: 1, fields: { status: 'approved' } },
      },
      { kind: 'answer', text: 'ok', access_token: 'secret' },
    ])
      expect(aiOutputSchema.safeParse(output).success).toBe(false);
    expect(
      aiOutputSchema.parse({
        kind: 'tool_proposal',
        tool: 'registration.open',
        arguments: { registration_id: 1 },
      }).kind,
    ).toBe('tool_proposal');
  });
});
describe('frontend permission gates', () => {
  it.each([
    ['participant', 'global', null, false, false],
    ['competition_admin', 'edition', 1, false, false],
    ['competition_admin', 'competition', 1, true, false],
    ['platform_admin', 'global', null, true, true],
  ])('scopes competition registry for %s / %s', (role, scope_type, scope_id, view, create) => {
    const account = meSchema.parse({
      ...actor,
      grants: [
        { role, scope_type, scope_id, permissions: ['competition:read', 'competition:create'] },
      ],
    });
    expect(mayViewCompetitionRegistry(account)).toBe(view);
    expect(mayCreateCompetition(account)).toBe(create);
  });

  it('permits only supplied grants and removes access when actor clears', () => {
    expect(mayEnter(actor, ['registration:create'])).toBe(true);
    expect(mayEnter(actor, ['approval:review_single'])).toBe(false);
    expect(mayEnter(null, ['registration:create'])).toBe(false);
    expect(mayRenderPrivate(true, false)).toBe(false);
    expect(mayRenderPrivate(true, true)).toBe(true);
    expect(mayRenderPrivate(false, false)).toBe(true);
  });
});
