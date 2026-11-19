import { z } from 'zod';
import { request } from './client';
import {
  registerRequestSchema,
  registerResultSchema,
  resetPasswordRequestSchema,
  verificationRequestSchema,
} from './authSchemas';
import {
  competitionDraftSchema,
  competitionSchema,
  draftFieldsSchema,
  editionDraftSchema,
  editionSchema,
  idSchema,
  loginSchema,
  managedCompetitionSchema,
  managedEditionSchema,
  managedSeasonSchema,
  meSchema,
  orgMemberSchema,
  orgSchema,
  pageSchema,
  preferencesSchema,
  registrationNoticeSchema,
  registrationSchema,
  seasonRegistrationSchema,
  seasonDraftSchema,
  seasonSchema,
  teamCreateSchema,
  teamRequestSchema,
  teamSchema,
  tokenSchema,
} from './schemas';

const positiveVersion = z.object({ version: z.number().int().positive() }).strict();
const reviewSchema = z
  .object({
    action: z.enum(['approve', 'reject', 'return']),
    comment: z.string().max(2000),
    submission_no: z.number().int().positive(),
  })
  .strict()
  .refine((v) => v.action === 'approve' || v.comment.trim().length > 0);
export const api = {
  login: (body: unknown) => request('POST', '/auth/login', tokenSchema, loginSchema.parse(body)),
  sendVerificationCode: (body: unknown) =>
    request('POST', '/auth/verify-code/send', z.null(), verificationRequestSchema.parse(body)),
  register: (body: unknown) =>
    request('POST', '/auth/register', registerResultSchema, registerRequestSchema.parse(body)),
  resetPassword: (body: unknown) =>
    request('POST', '/auth/password/reset', z.null(), resetPasswordRequestSchema.parse(body)),
  me: () => request('GET', '/me', meSchema),
  notifications: (page = 1) =>
    request('GET', `/me/notifications?page=${page}`, pageSchema(registrationNoticeSchema)),
  readNotification: (id: number) =>
    request('POST', `/me/notifications/${idSchema.parse(id)}/read`, registrationNoticeSchema, {}),
  preferences: (body: unknown) =>
    request('PATCH', '/me/preferences', preferencesSchema, preferencesSchema.parse(body)),
  changePassword: (body: unknown) =>
    request(
      'POST',
      '/auth/password/change',
      tokenSchema,
      z
        .object({
          old_password: z.string().min(1).max(256),
          new_password: z.string().min(12).max(256),
        })
        .strict()
        .parse(body),
    ),
  season: () => request('GET', '/seasons/current', seasonSchema.nullable()),
  managedSeasons: (page = 1) =>
    request('GET', `/seasons?page=${page}`, pageSchema(managedSeasonSchema)),
  createSeason: (body: unknown) =>
    request('POST', '/seasons', managedSeasonSchema, seasonDraftSchema.parse(body)),
  activateSeason: (id: number) =>
    request('POST', `/seasons/${idSchema.parse(id)}/activate`, managedSeasonSchema, {}),
  setCurrentSeason: (id: number) =>
    request('POST', `/seasons/${idSchema.parse(id)}/set-current`, managedSeasonSchema, {}),
  competitions: (page = 1) =>
    request('GET', `/public/competitions?page=${page}`, pageSchema(competitionSchema)),
  managedCompetitions: (page = 1) =>
    request('GET', `/competitions?page=${page}`, pageSchema(managedCompetitionSchema)),
  createCompetition: (body: unknown) =>
    request('POST', '/competitions', managedCompetitionSchema, competitionDraftSchema.parse(body)),
  managedEditions: (competition: number, page = 1) =>
    request(
      'GET',
      `/competitions/${idSchema.parse(competition)}/editions?page=${page}`,
      pageSchema(managedEditionSchema),
    ),
  eligibleEditionSeasons: (competition: number, page = 1) =>
    request(
      'GET',
      `/competitions/${idSchema.parse(competition)}/edition-seasons?page=${page}&page_size=100`,
      pageSchema(managedSeasonSchema),
    ),
  createEdition: (competition: number, body: unknown) =>
    request(
      'POST',
      `/competitions/${idSchema.parse(competition)}/editions`,
      managedEditionSchema,
      editionDraftSchema.parse(body),
    ),
  edition: (id: number) => request('GET', `/public/editions/${idSchema.parse(id)}`, editionSchema),
  teams: (page = 1) => request('GET', `/teams?page=${page}`, pageSchema(teamSchema)),
  orgs: () => request('GET', '/orgs', pageSchema(orgSchema)),
  orgMembers: (id: number) =>
    request('GET', `/orgs/${idSchema.parse(id)}/members`, pageSchema(orgMemberSchema)),
  teamRequests: () => request('GET', '/team-change-requests', pageSchema(teamRequestSchema)),
  createTeamRequest: (body: unknown) =>
    request('POST', '/team-change-requests', teamRequestSchema, teamCreateSchema.parse(body)),
  submitTeamRequest: (id: number) =>
    request('POST', `/team-change-requests/${idSchema.parse(id)}/submit`, teamRequestSchema, {}),
  reviewTeamRequest: (id: number, body: unknown) =>
    request(
      'POST',
      `/team-change-requests/${idSchema.parse(id)}/review`,
      teamRequestSchema,
      z
        .object({ action: z.enum(['approve', 'reject', 'return']), comment: z.string().max(2000) })
        .strict()
        .refine((v) => v.action === 'approve' || !!v.comment.trim())
        .parse(body),
    ),
  seasonRegistrations: () =>
    request('GET', '/team-season-registrations', pageSchema(seasonRegistrationSchema)),
  createSeasonRegistration: (body: unknown) =>
    request(
      'POST',
      '/team-season-registrations',
      seasonRegistrationSchema,
      z.object({ team_id: idSchema, season_id: idSchema }).strict().parse(body),
    ),
  submitSeasonRegistration: (id: number) =>
    request(
      'POST',
      `/team-season-registrations/${idSchema.parse(id)}/submit`,
      seasonRegistrationSchema,
      {},
    ),
  reviewSeasonRegistration: (id: number, action: 'approve' | 'reject', comment: string) =>
    request(
      'POST',
      `/team-season-registrations/${idSchema.parse(id)}/review`,
      seasonRegistrationSchema,
      z
        .object({ action: z.enum(['approve', 'reject']), comment: z.string().max(2000) })
        .strict()
        .parse({ action, comment }),
    ),
  registrations: (edition?: number, page = 1, status = '') =>
    request(
      'GET',
      `/registrations?page=${page}${edition ? `&edition=${idSchema.parse(edition)}` : ''}${status ? `&status=${encodeURIComponent(status)}` : ''}`,
      pageSchema(registrationSchema),
    ),
  myRegistrations: (edition: number, page = 1) =>
    request(
      'GET',
      `/editions/${idSchema.parse(edition)}/registrations?page=${page}`,
      pageSchema(registrationSchema),
    ),
  registration: (id: number) =>
    request('GET', `/registrations/${idSchema.parse(id)}`, registrationSchema),
  createRegistration: (edition: number, body: unknown) =>
    request('POST', `/editions/${idSchema.parse(edition)}/registrations`, registrationSchema, {
      ...draftFieldsSchema.parse(body),
      submit: false,
    }),
  saveRegistration: (id: number, version: number, body: unknown) => {
    const fields = draftFieldsSchema.parse(body);
    return request('PATCH', `/registrations/${idSchema.parse(id)}`, registrationSchema, {
      offering_id: fields.offering_id,
      coach_user_id: fields.coach_user_id,
      selected_school_level: fields.selected_school_level,
      contact: fields.contact,
      form_data: fields.form_data,
      consents: fields.consents,
      ...positiveVersion.parse({ version }),
    });
  },
  registrationAction: (
    id: number,
    action: 'submit' | 'resubmit' | 'cancel-review' | 'withdraw',
    version: number,
    key?: string,
  ) =>
    request(
      'POST',
      `/registrations/${idSchema.parse(id)}/${action}`,
      registrationSchema,
      positiveVersion.parse({ version }),
      key ? { 'Idempotency-Key': key } : undefined,
    ),
  reviewRegistration: (id: number, body: unknown) =>
    request(
      'POST',
      `/registrations/${idSchema.parse(id)}/approval`,
      registrationSchema,
      reviewSchema.parse(body),
    ),
};
