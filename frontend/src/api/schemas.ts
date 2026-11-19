import { z } from 'zod';
import type { components } from './generated';

export const idSchema = z.number().int().positive().safe();
const nullableId = idSchema.nullable();
const text = z.string();
const schoolLevel = z.enum(['ES', 'MS', 'HS', 'U']);
export const localeSchema = z.enum(['zh-CN', 'en-US']);
export const themeSchema = z.enum(['light', 'dark', 'system']);
export const grantSchema = z
  .object({
    role: text.min(1).max(64),
    scope_type: z.enum(['global', 'org', 'competition', 'edition']),
    scope_id: nullableId,
    permissions: z.array(z.string().regex(/^[a-z_]+:[a-z_]+$/)).max(200),
  })
  .strict()
  .refine((g) => (g.scope_type === 'global') === (g.scope_id === null));
export const meSchema = z
  .object({
    user: z
      .object({
        id: idSchema,
        username: text,
        email: z.string().email().nullable(),
        must_change_password: z.boolean(),
      })
      .strict(),
    profile: z
      .object({
        real_name: text,
        person_type: text,
        school_level: schoolLevel.nullable(),
        grade: text.nullable(),
      })
      .strict()
      .nullable(),
    grants: z.array(grantSchema),
    locale: localeSchema,
    theme: themeSchema,
  })
  .strict();
export const loginSchema = z.discriminatedUnion('login_type', [
  z
    .object({
      login_type: z.literal('email'),
      email: z.string().email().max(255),
      password: text.min(1).max(256),
    })
    .strict(),
  z
    .object({
      login_type: z.literal('document'),
      document_type: z.enum(['id_card', 'passport']),
      document_country: z.string().regex(/^[A-Z]{2}$/),
      document_number: text.min(1).max(32),
      password: text.min(1).max(256),
    })
    .strict(),
]);
export const tokenSchema = z
  .object({ access: text.min(1), expires_in: z.number().int().positive() })
  .strict();
export const csrfSchema = z.object({ csrf_token: text.min(1) }).strict();
export const preferencesSchema = z.object({ locale: localeSchema, theme: themeSchema }).strict();
export const seasonSchema = z
  .object({
    id: idSchema,
    name: text,
    start_date: z.string().date(),
    end_date: z.string().date(),
    status: z.enum(['draft', 'active', 'archived']),
  })
  .strict();
export const managedSeasonSchema = seasonSchema.extend({
  code: text.min(1).max(32),
  is_default: z.boolean(),
}) satisfies z.ZodType<components['schemas']['ManagedSeason']>;
export const seasonDraftSchema = z
  .object({
    code: text.trim().regex(/^[A-Z0-9][A-Z0-9-]{0,31}$/),
    name: text.trim().min(1).max(64),
    start_date: text.date(),
    end_date: text.date(),
  })
  .strict()
  .refine((season) => season.start_date <= season.end_date, {
    path: ['end_date'],
  }) satisfies z.ZodType<components['schemas']['SeasonDraftRequest']>;
export type ManagedSeason = components['schemas']['ManagedSeason'];

export const offeringSchema = z
  .object({
    id: idSchema,
    event_id: idSchema,
    event_code: text,
    event_name: text,
    group_id: idSchema,
    group_name: text,
    school_level: schoolLevel.nullable(),
    enrollment_type: z.enum(['individual', 'team', 'both']),
    min_members: z.number().int().nonnegative(),
    max_members: z.number().int().nonnegative(),
    require_coach: z.boolean(),
    required_materials: z.array(text),
    is_enabled: z.boolean(),
  })
  .strict()
  .refine((o) => o.min_members <= o.max_members);
export const editionSchema = z
  .object({
    id: idSchema,
    competition_id: idSchema,
    season_id: idSchema,
    name: text,
    status: z.enum(['draft', 'published', 'closed']),
    approval_mode: z.literal('single'),
    enroll_start: z.string().datetime({ offset: true }),
    enroll_end: z.string().datetime({ offset: true }),
    start_date: z.string().datetime({ offset: true }),
    end_date: z.string().datetime({ offset: true }),
    venue: text,
    offerings: z.array(offeringSchema),
  })
  .strict();
const editionClock = text
  .datetime({ local: true })
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/);
export const editionDraftSchema = z
  .object({
    season_id: idSchema,
    edition_no: z.number().int().min(1).max(9999),
    year: z.number().int().min(1).max(9999),
    name: text.trim().min(1).max(128),
    venue: text.trim().min(1).max(255),
    time_zone: z.literal('Asia/Shanghai'),
    enroll_start: editionClock,
    enroll_end: editionClock,
    start_date: editionClock,
    end_date: editionClock,
  })
  .strict() satisfies z.ZodType<components['schemas']['EditionDraftRequest']>;
export const managedEditionSchema = editionSchema
  .omit({ approval_mode: true, offerings: true })
  .extend({
    edition_no: z.number().int().positive(),
    year: z.number().int().positive(),
  }) satisfies z.ZodType<components['schemas']['ManagedEdition']>;
export type ManagedEdition = components['schemas']['ManagedEdition'];

export const eventTypeSummarySchema = z
  .object({
    code: text.min(1).max(16),
    name: text.min(1).max(64),
  })
  .strict() satisfies z.ZodType<components['schemas']['EventTypeSummary']>;
const editionEventFields = z
  .object({
    event_code: text.regex(/^[A-Z0-9][A-Z0-9-]{0,15}$/),
    name: text.trim().min(1).max(64),
    min_members: z.number().int().min(1).max(2147483647),
    max_members: z.number().int().min(1).max(2147483647),
    coach_required: z.boolean(),
  })
  .strict();
export const editionEventDraftSchema = editionEventFields.refine(
  (item) => item.min_members <= item.max_members,
  { path: ['max_members'] },
) satisfies z.ZodType<components['schemas']['EditionEventDraftRequest']>;
export const managedEventSchema = editionEventFields.extend({
  id: idSchema,
  event_code: text.min(1).max(16),
  status: z.enum(['enabled', 'disabled']),
}) satisfies z.ZodType<components['schemas']['ManagedEvent']>;
export type ManagedEvent = components['schemas']['ManagedEvent'];
export type EventTypeSummary = components['schemas']['EventTypeSummary'];

export const groupDraftSchema = z
  .object({
    code: text.trim().regex(/^[A-Z0-9][A-Z0-9-]{0,7}$/),
    name: text.trim().min(1).max(64),
    school_level: schoolLevel.nullable(),
    enrollment_type: z.enum(['individual', 'team', 'both']),
    grade_limits: z.array(text.trim().min(1).max(32)).max(32),
  })
  .strict() satisfies z.ZodType<components['schemas']['GroupDraftRequest']>;
export const managedGroupSchema = groupDraftSchema.extend({
  id: idSchema,
  code: text.min(1).max(8),
  status: z.enum(['enabled', 'disabled']),
}) satisfies z.ZodType<components['schemas']['ManagedGroup']>;
export type ManagedGroup = components['schemas']['ManagedGroup'];

export const offeringDraftSchema = z
  .object({ event_id: idSchema, group_id: idSchema })
  .strict() satisfies z.ZodType<components['schemas']['OfferingDraftRequest']>;
export const managedOfferingSchema = offeringDraftSchema.extend({
  id: idSchema,
  status: z.enum(['enabled', 'disabled']),
  is_enabled: z.boolean(),
}) satisfies z.ZodType<components['schemas']['ManagedOffering']>;
export type ManagedOffering = components['schemas']['ManagedOffering'];

export const competitionSchema = z
  .object({
    id: idSchema,
    public_code: text,
    name: text,
    summary: text,
    status: z.literal('published'),
    editions: z.array(editionSchema),
  })
  .strict();
export const managedCompetitionSchema = z
  .object({
    id: idSchema,
    public_code: text.min(1).max(32),
    name: text.min(1).max(128),
    summary: text,
    status: z.enum(['draft', 'published', 'archived']),
  })
  .strict() satisfies z.ZodType<components['schemas']['ManagedCompetition']>;
export const competitionDraftSchema = z
  .object({ name: text.trim().min(1).max(128), summary: text.trim().max(2000) })
  .strict() satisfies z.ZodType<components['schemas']['CompetitionDraftRequest']>;
export type ManagedCompetition = components['schemas']['ManagedCompetition'];
export const memberSchema = z
  .object({
    user_id: idSchema,
    real_name: text,
    role: z.enum(['captain', 'member']),
    school_level: schoolLevel.nullable(),
    grade: text.nullable(),
  })
  .strict();
export const requestStatusSchema = z.enum([
  'draft',
  'submitted',
  'approved',
  'returned',
  'rejected',
  'withdrawn',
]);
export const seasonRegistrationSchema = z
  .object({
    id: idSchema,
    team_id: idSchema,
    season_id: idSchema,
    status: z.enum(['draft', 'submitted', 'approved', 'rejected', 'withdrawn', 'revoked']),
    submitted_by: idSchema,
    reviewer_id: nullableId,
    comment: text,
  })
  .strict();
export const teamSchema = z
  .object({
    id: idSchema,
    team_code: text,
    event_code: text,
    name: text,
    org_id: idSchema,
    coach_id: nullableId,
    captain_id: nullableId,
    approved_revision_id: nullableId,
    membership_version: z.number().int().positive(),
    status: z.enum(['active', 'disbanded']),
    members: z.array(memberSchema).optional(),
    season_registrations: z.array(seasonRegistrationSchema),
  })
  .strict();
export const orgSchema = z
  .object({ id: idSchema, name: text, path: text, status: z.enum(['active', 'suspended']) })
  .strict();
export const orgMemberSchema = z
  .object({
    id: idSchema,
    user_id: idSchema,
    real_name: text,
    person_type: text,
    school_level: schoolLevel.nullable(),
    grade: text.nullable(),
  })
  .strict();
export const proposalSchema = z
  .object({
    name: text.trim().min(1).max(128),
    coach_id: nullableId,
    captain_id: nullableId,
    members: z
      .array(z.object({ user_id: idSchema, role: z.enum(['captain', 'member']) }).strict())
      .min(1)
      .max(100),
  })
  .strict();
export const teamRequestSchema = z
  .object({
    id: idSchema,
    request_kind: z.enum(['create', 'update']),
    team_id: nullableId,
    org_id: idSchema,
    status: requestStatusSchema,
    submitted_by: idSchema,
    base_revision_id: nullableId,
    base_membership_version: z.number().int().positive(),
    registration_season_id: nullableId,
    proposal: proposalSchema,
    comment: text,
  })
  .strict();
export const teamCreateSchema = z
  .object({
    request_kind: z.literal('create'),
    org_id: idSchema,
    team_code: text.trim().min(1).max(32),
    event_code: text.trim().min(1).max(16),
    registration_season_id: idSchema,
    proposal: proposalSchema,
  })
  .strict();
const contactSchema = z
  .object({
    name: text.trim().min(1).max(64),
    phone: text.trim().min(1).max(20),
    email: z.string().email().nullable(),
  })
  .strict();
export const draftFieldsSchema = z
  .object({
    offering_id: idSchema,
    enrollment_kind: z.enum(['individual', 'team']),
    team_id: idSchema.optional(),
    coach_user_id: nullableId,
    selected_school_level: schoolLevel.nullable(),
    contact: contactSchema,
    form_data: z.object({ project_title: text.trim().max(200) }).strict(),
    consents: z.object({ document_usage: z.boolean() }).strict(),
  })
  .strict()
  .refine((d) => (d.enrollment_kind === 'team') === (d.team_id !== undefined));
export const approvalSchema = z
  .object({
    id: idSchema,
    submission_no: z.number().int().positive(),
    action: z.enum(['approve', 'reject', 'return', 'withdraw', 'cancel_review']),
    comment: text,
    reviewer_id: idSchema,
    created_at: z.string().datetime({ offset: true }),
  })
  .strict();
export const registrationSchema = z
  .object({
    id: idSchema,
    batch_no: text,
    edition_id: idSchema,
    offering_id: idSchema,
    enrollment_kind: z.enum(['individual', 'team']),
    team_id: nullableId,
    individual_user_id: nullableId,
    org_id: idSchema,
    submitted_by: idSchema,
    coach_user_id: nullableId,
    status: z.enum(['draft', 'pending_review', 'returned', 'rejected', 'approved', 'withdrawn']),
    current_submission_no: z.number().int().positive().nullable(),
    approved_submission_no: z.number().int().positive().nullable(),
    version: z.number().int().positive(),
    selected_school_level: schoolLevel.nullable(),
    contact: contactSchema.optional(),
    form_data: z.object({ project_title: text }).strict().optional(),
    consents: z.object({ document_usage: z.boolean() }).strict().optional(),
    members: z.array(memberSchema),
    files: z.array(z.object({ id: idSchema, material_type: text, name: text }).strict()),
    approval_records: z.array(approvalSchema),
    can_edit: z.boolean(),
  })
  .strict();
export const registrationNoticeSchema = z
  .object({
    id: idSchema,
    registration_id: idSchema,
    submission_no: z.number().int().positive(),
    kind: z.enum(['submitted', 'approved', 'rejected', 'returned']),
    created_at: z.string().datetime({ offset: true }),
    read_at: z.string().datetime({ offset: true }).nullable(),
  })
  .strict() satisfies z.ZodType<components['schemas']['RegistrationNotice']>;
export type RegistrationNotice = components['schemas']['RegistrationNotice'];

export function pageSchema<T extends z.ZodTypeAny>(item: T) {
  return z
    .object({
      items: z.array(item).max(100),
      page: z.number().int().positive(),
      page_size: z.number().int().positive().max(100),
      total: z.number().int().nonnegative(),
    })
    .strict();
}
export function envelopeSchema<T extends z.ZodTypeAny>(data: T) {
  return z.object({ code: z.literal(0), message: text, data, request_id: text.min(1) }).strict();
}
export const errorSchema = z
  .object({
    code: z.number().int().positive(),
    message: text,
    data: z.null(),
    request_id: text.min(1),
    errors: z.record(z.string(), z.array(text)).optional(),
  })
  .strict();
export const aiOutputSchema = z.union([
  z.object({ kind: z.literal('answer'), text: text.min(1).max(4000) }).strict(),
  z
    .object({
      kind: z.literal('tool_proposal'),
      tool: z.literal('registration.open'),
      arguments: z.object({ registration_id: idSchema }).strict(),
    })
    .strict(),
  z
    .object({
      kind: z.literal('tool_proposal'),
      tool: z.literal('registration.update_draft'),
      arguments: z
        .object({
          registration_id: idSchema,
          version: z.number().int().positive(),
          fields: z.object({ selected_school_level: schoolLevel }).strict(),
        })
        .strict(),
    })
    .strict(),
]);
export type Me = components['schemas']['Me'];
export type Team = components['schemas']['Team'];
export type Edition = components['schemas']['Edition'];
export type Registration = components['schemas']['Registration'];
export type TeamRequest = components['schemas']['TeamChangeRequest'];
// Compilation fails if a required response field changes in generated OpenAPI types.
export const checkedContractSchemas = {
  me: meSchema,
  team: teamSchema,
  edition: editionSchema,
  registration: registrationSchema,
  teamRequest: teamRequestSchema,
  competition: competitionSchema,
  season: seasonSchema,
} satisfies {
  me: z.ZodType<Me>;
  team: z.ZodType<Team>;
  edition: z.ZodType<Edition>;
  registration: z.ZodType<Registration>;
  teamRequest: z.ZodType<TeamRequest>;
  competition: z.ZodType<components['schemas']['Competition']>;
  season: z.ZodType<components['schemas']['Season']>;
};
