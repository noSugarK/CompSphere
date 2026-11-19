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
  editionDetailsSchema,
  editionDraftSchema,
  editionEventDraftSchema,
  editionEventUpdateSchema,
  editionPublicationChecksSchema,
  editionSchema,
  eventTypeSummarySchema,
  groupDraftSchema,
  idSchema,
  loginSchema,
  managedCompetitionSchema,
  managedEditionSchema,
  managedEventSchema,
  managedGroupSchema,
  managedOfferingSchema,
  managedSeasonSchema,
  meSchema,
  orgMemberSchema,
  offeringDraftSchema,
  offeringOverridesSchema,
  offeringSchema,
  orgSchema,
  pageSchema,
  preferencesSchema,
  registrationNoticeSchema,
  registrationSchema,
  registrationSubmissionSchema,
  reviewQueueItemSchema,
  reviewQueueOptionSchema,
  type ReviewQueueFilters,
  type ReviewQueueOptionQuery,
  seasonRegistrationSchema,
  seasonDraftSchema,
  seasonSchema,
  teamCreateSchema,
  teamRequestSchema,
  teamSchema,
  tokenSchema,
} from './schemas';

const positiveVersion = z.object({ version: z.number().int().positive() }).strict();
function queryString(parameters: ReviewQueueFilters | ReviewQueueOptionQuery) {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(parameters)) {
    if (value !== undefined && value !== '') query.set(name, String(value));
  }
  return query.toString();
}
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
  managedEdition: (id: number) =>
    request('GET', `/editions/${idSchema.parse(id)}`, managedEditionSchema),
  updateEdition: (id: number, body: unknown) =>
    request(
      'PATCH',
      `/editions/${idSchema.parse(id)}`,
      managedEditionSchema,
      editionDetailsSchema.parse(body),
    ),
  editionPublicationChecks: (id: number) =>
    request(
      'GET',
      `/editions/${idSchema.parse(id)}/publication-checks`,
      editionPublicationChecksSchema,
    ),
  publishEdition: (id: number) =>
    request('POST', `/editions/${idSchema.parse(id)}/publish`, managedEditionSchema, {}),
  publishCompetition: (id: number) =>
    request('POST', `/competitions/${idSchema.parse(id)}/publish`, managedCompetitionSchema, {}),
  editionEventTypes: (id: number, page = 1) =>
    request(
      'GET',
      `/editions/${idSchema.parse(id)}/event-types?page=${page}&page_size=100`,
      pageSchema(eventTypeSummarySchema),
    ),
  editionEvents: (id: number, page = 1, pageSize = 20) =>
    request(
      'GET',
      `/editions/${idSchema.parse(id)}/events?page=${page}&page_size=${pageSize}`,
      pageSchema(managedEventSchema),
    ),
  createEditionEvent: (id: number, body: unknown) =>
    request(
      'POST',
      `/editions/${idSchema.parse(id)}/events`,
      managedEventSchema,
      editionEventDraftSchema.parse(body),
    ),
  updateEditionEvent: (id: number, body: unknown) =>
    request(
      'PATCH',
      `/events/${idSchema.parse(id)}`,
      managedEventSchema,
      editionEventUpdateSchema.parse(body),
    ),
  deleteEditionEvent: (id: number) => request('DELETE', `/events/${idSchema.parse(id)}`, z.null()),
  setEditionEventState: (id: number, action: 'enable' | 'disable') =>
    request('POST', `/events/${idSchema.parse(id)}/${action}`, managedEventSchema, {}),
  editionGroups: (id: number, page = 1, pageSize = 20) =>
    request(
      'GET',
      `/editions/${idSchema.parse(id)}/groups?page=${page}&page_size=${pageSize}`,
      pageSchema(managedGroupSchema),
    ),
  createGroup: (id: number, body: unknown) =>
    request(
      'POST',
      `/editions/${idSchema.parse(id)}/groups`,
      managedGroupSchema,
      groupDraftSchema.parse(body),
    ),
  updateGroup: (id: number, body: unknown) =>
    request(
      'PATCH',
      `/groups/${idSchema.parse(id)}`,
      managedGroupSchema,
      groupDraftSchema.parse(body),
    ),
  deleteGroup: (id: number) => request('DELETE', `/groups/${idSchema.parse(id)}`, z.null()),
  setGroupState: (id: number, action: 'enable' | 'disable') =>
    request('POST', `/groups/${idSchema.parse(id)}/${action}`, managedGroupSchema, {}),
  editionOfferings: (id: number, page = 1) =>
    request(
      'GET',
      `/editions/${idSchema.parse(id)}/offerings?page=${page}&page_size=100`,
      pageSchema(managedOfferingSchema),
    ),
  createOffering: (id: number, body: unknown) =>
    request(
      'POST',
      `/editions/${idSchema.parse(id)}/offerings`,
      managedOfferingSchema,
      offeringDraftSchema.parse(body),
    ),
  setOfferingState: (id: number, action: 'enable' | 'disable') =>
    request('POST', `/offerings/${idSchema.parse(id)}/${action}`, managedOfferingSchema, {}),
  updateOffering: (id: number, body: unknown) =>
    request(
      'PATCH',
      `/offerings/${idSchema.parse(id)}`,
      managedOfferingSchema,
      offeringOverridesSchema.parse(body),
    ),
  deleteOffering: (id: number) => request('DELETE', `/offerings/${idSchema.parse(id)}`, z.null()),
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
  availableOfferings: async (edition: number, team?: number) => {
    const path = `/editions/${idSchema.parse(edition)}/available-offerings?page_size=100${team === undefined ? '' : `&team_id=${idSchema.parse(team)}`}`;
    const schema = pageSchema(offeringSchema);
    const first = await request('GET', `${path}&page=1`, schema);
    const items = [...first.items];
    for (let page = 2; page <= Math.ceil(first.total / first.page_size); page += 1) {
      items.push(...(await request('GET', `${path}&page=${page}`, schema)).items);
    }
    return items;
  },
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
  registrations: (filters: ReviewQueueFilters) =>
    request('GET', `/registrations?${queryString(filters)}`, pageSchema(reviewQueueItemSchema)),
  reviewQueueOptions: (query: ReviewQueueOptionQuery) =>
    request(
      'GET',
      `/registrations/filter-options?${queryString(query)}`,
      pageSchema(reviewQueueOptionSchema),
    ),
  myRegistrations: (edition: number, page = 1) =>
    request(
      'GET',
      `/editions/${idSchema.parse(edition)}/registrations?page=${page}`,
      pageSchema(registrationSchema),
    ),
  registration: (id: number) =>
    request('GET', `/registrations/${idSchema.parse(id)}`, registrationSchema),
  registrationSubmissions: (id: number, page: number) =>
    request(
      'GET',
      `/registrations/${idSchema.parse(id)}/submissions?page=${page}`,
      pageSchema(registrationSubmissionSchema),
    ),
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
