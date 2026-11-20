import { describe, expect, it } from 'vitest';
import {
  aiOutputSchema,
  bulkReviewResultSchema,
  csrfSchema,
  editionDetailsSchema,
  editionDraftSchema,
  envelopeSchema,
  idSchema,
  identityChangeSchema,
  loginSchema,
  meSchema,
  pageSchema,
  publicRosterEntrySchema,
  publicRosterSchema,
  reviewedMemberSchema,
  seasonDraftSchema,
  seasonSchema,
  studentAccountSchema,
} from '../src/api/schemas';
import {
  mayCreateCompetition,
  mayCreateEdition,
  mayEnter,
  mayRenderPrivate,
  mayUnarchiveCompetition,
  mayViewCompetitionRegistry,
} from '../src/utils/permissions';
import {
  competitionUpdateSchema,
  managedCompetitionDetailSchema,
  seasonUpdateSchema,
} from '../src/api/schemas';

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
  it('keeps student and identity responses to the last four characters', () => {
    const account = {
      id: 1,
      username: 'u_1',
      email: null,
      status: 'active',
      must_change_password: true,
      initial_password_expires_at: null,
      document_type: 'id_card',
      document_country: 'CN',
      document_last4: '0010',
      real_name: 'a',
      org_id: 1,
    };
    expect(studentAccountSchema.safeParse(account).success).toBe(true);
    expect(
      studentAccountSchema.safeParse({ ...account, document_number: '1'.repeat(18) }).success,
    ).toBe(false);
    expect(
      identityChangeSchema.safeParse({
        id: 1,
        user_id: 1,
        status: 'draft',
        base_identity_version: 0,
        new_document_type: 'id_card',
        new_document_country: 'CN',
        new_document_last4: '0010',
        has_old_document: false,
        submitted_by: 1,
        reviewer_id: null,
        comment: '',
        reviewed_at: null,
        created_at: 'x',
        new_document_number: 'secret',
      }).success,
    ).toBe(false);
  });
  it('rejects sensitive keys in a public roster payload', () => {
    const base = { edition_id: 1, edition_name: 'e', publish_fields: ['team_code'], entries: [] };
    expect(publicRosterSchema.safeParse(base).success).toBe(true);
    expect(publicRosterSchema.safeParse({ ...base, contact_phone: '1' }).success).toBe(false);
    expect(
      publicRosterEntrySchema.safeParse({ team_code: 'A', document_number: '1' }).success,
    ).toBe(false);
  });
  it('keeps reviewed member fields capped at document last 4', () => {
    const base = { user_id: 1, real_name: 'a', role: 'member', school_level: null, grade: null };
    expect(reviewedMemberSchema.safeParse({ ...base, document_last4: '0027' }).success).toBe(true);
    expect(reviewedMemberSchema.safeParse({ ...base, document_number: '123456789' }).success).toBe(
      false,
    );
    expect(reviewedMemberSchema.safeParse({ ...base, snapshot_enc: 'x' }).success).toBe(false);
  });
  it('does not accept a bulk review failure as a completed status change', () => {
    expect(
      bulkReviewResultSchema.safeParse({ registration_id: 1, code: 0, status: 'approved' }).success,
    ).toBe(true);
    expect(
      bulkReviewResultSchema.safeParse({ registration_id: 1, code: 40906, status: null }).success,
    ).toBe(true);
    expect(
      bulkReviewResultSchema.safeParse({ registration_id: 1, code: 40906, status: 'approved' })
        .success,
    ).toBe(false);
    expect(
      bulkReviewResultSchema.safeParse({ registration_id: 1, code: 0, status: null }).success,
    ).toBe(false);
  });
  it('requires an explicit zone for local edition times', () => {
    const edition = {
      season_id: 1,
      edition_no: 1,
      year: 2028,
      name: 'Test edition',
      venue: 'Test venue',
      time_zone: 'Asia/Shanghai',
      enroll_start: '2028-01-01T09:00',
      enroll_end: '2028-02-01T09:00',
      start_date: '2028-02-01T10:00',
      end_date: '2028-02-01T17:00',
    };
    expect(editionDraftSchema.parse(edition)).toEqual(edition);
    expect(editionDraftSchema.safeParse({ ...edition, time_zone: undefined }).success).toBe(false);
    expect(
      editionDraftSchema.safeParse({ ...edition, start_date: '2028-02-01T02:00Z' }).success,
    ).toBe(false);
  });
  it('allows partial edition detail edits without accepting identity fields', () => {
    const patch = {
      name: 'Updated name',
      start_date: '2028-02-01T10:00',
      time_zone: 'Asia/Shanghai',
    };
    expect(editionDetailsSchema.parse(patch)).toEqual(patch);
    expect(editionDetailsSchema.safeParse({ ...patch, season_id: 1 }).success).toBe(false);
    expect(editionDetailsSchema.safeParse({ venue: '' }).success).toBe(false);
  });
  it('keeps cross-year season dates as calendar strings and rejects inverted ranges', () => {
    const season = {
      code: '2027-2028',
      name: 'QA season',
      start_date: '2027-09-01',
      end_date: '2028-08-31',
    };
    expect(seasonDraftSchema.parse(season)).toEqual(season);
    expect(seasonDraftSchema.safeParse({ ...season, end_date: '2026-01-01' }).success).toBe(false);
  });
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

  it('scopes competition restore to the global platform role only', () => {
    const archive = ['competition:read', 'competition:archive'];
    const scoped = meSchema.parse({
      ...actor,
      grants: [
        { role: 'competition_admin', scope_type: 'competition', scope_id: 1, permissions: archive },
      ],
    });
    const platform = meSchema.parse({
      ...actor,
      grants: [
        { role: 'platform_admin', scope_type: 'global', scope_id: null, permissions: archive },
      ],
    });
    expect(mayUnarchiveCompetition(scoped)).toBe(false);
    expect(mayUnarchiveCompetition(platform)).toBe(true);
  });

  it('validates season, competition and archive JSON boundaries', () => {
    expect(seasonUpdateSchema.parse({ name: 'Next', start_date: '2029-09-01' })).toEqual({
      name: 'Next',
      start_date: '2029-09-01',
    });
    expect(competitionUpdateSchema.safeParse({ status: 'published' }).success).toBe(false);
    expect(competitionUpdateSchema.safeParse({ category: 'esports' }).success).toBe(false);
    expect(competitionUpdateSchema.parse({ category: null, level: 'province' })).toEqual({
      category: null,
      level: 'province',
    });
    const detail = managedCompetitionDetailSchema.parse({
      id: 7,
      public_code: 'CMP-7',
      name: 'QA',
      summary: '',
      status: 'archived',
      category: null,
      level: null,
    });
    expect(detail.category).toBeNull();
  });

  it('does not inherit edition creation up or across a competition', () => {
    const grant = {
      role: 'competition_admin',
      scope_type: 'competition',
      scope_id: 1,
      permissions: ['edition:create'],
    };
    const competition = meSchema.parse({ ...actor, grants: [grant] });
    const edition = meSchema.parse({ ...actor, grants: [{ ...grant, scope_type: 'edition' }] });
    expect(mayCreateEdition(competition, 1)).toBe(true);
    expect(mayCreateEdition(competition, 2)).toBe(false);
    expect(mayCreateEdition(edition, 1)).toBe(false);
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
