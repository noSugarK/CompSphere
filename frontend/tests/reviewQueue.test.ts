import { describe, expect, it } from 'vitest';
import { readReviewQueueQuery, writeReviewQueueQuery } from '../src/utils/reviewQueue';

describe('review queue navigation', () => {
  it('restores filters and pagination from a detail return link', () => {
    const filters = readReviewQueueQuery({
      edition: '3',
      event: '4',
      group: '7',
      org: '8',
      status: 'all',
      page: '2',
      q: ' A1024 ',
      origin: 'reviews',
    });
    expect(writeReviewQueueQuery(filters)).toEqual({
      edition: 3,
      event: 4,
      group: 7,
      org: 8,
      status: 'all',
      page: 2,
      q: 'A1024',
    });
  });

  it('drops malformed and repeated route values and defaults to pending review', () => {
    const filters = readReviewQueueQuery({
      edition: ['1', '2'],
      event: '-1',
      group: '9007199254740992',
      status: 'unknown',
      page: '0',
      q: ['a', 'b'],
    });
    expect(filters).toMatchObject({ status: 'pending_review', page: 1 });
    expect(
      Object.values(writeReviewQueueQuery(filters)).every((value) => value === undefined),
    ).toBe(true);
  });
});
