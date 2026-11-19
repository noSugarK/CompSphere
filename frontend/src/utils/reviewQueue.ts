import type { LocationQuery, LocationQueryRaw } from 'vue-router';
import { idSchema, registrationStatusSchema, type ReviewQueueFilters } from '../api/schemas';

export const reviewDimensions = ['edition', 'event', 'group', 'org'] as const;
export type ReviewDimension = (typeof reviewDimensions)[number];
export type ReviewQueueNavigation = Omit<ReviewQueueFilters, 'page_size' | 'status'> & {
  status: NonNullable<ReviewQueueFilters['status']> | 'all';
  page: number;
};

export function readReviewQueueQuery(query: LocationQuery): ReviewQueueNavigation {
  const readId = (field: string) => {
    const value = query[field];
    if (typeof value !== 'string' || !/^\d+$/.test(value)) return undefined;
    return idSchema.safeParse(Number(value)).data;
  };
  return {
    edition: readId('edition'),
    event: readId('event'),
    group: readId('group'),
    org: readId('org'),
    q: typeof query.q === 'string' ? query.q.trim().slice(0, 80) : undefined,
    status:
      query.status === 'all'
        ? 'all'
        : (registrationStatusSchema.safeParse(query.status).data ?? 'pending_review'),
    page: readId('page') ?? 1,
  };
}

export function writeReviewQueueQuery(filters: ReviewQueueNavigation): LocationQueryRaw {
  return {
    edition: filters.edition,
    event: filters.event,
    group: filters.group,
    org: filters.org,
    q: filters.q?.trim() || undefined,
    status: filters.status === 'pending_review' ? undefined : filters.status,
    page: filters.page > 1 ? filters.page : undefined,
  };
}
