import { describe, expect, it } from 'vitest';
import { isOfferingOpen } from '../src/utils/offerings';

const offering = {
  is_enabled: true,
  enroll_start: '2026-11-19T09:00:00+08:00',
  enroll_end: '2026-11-19T09:30:00+08:00',
  quota: 0,
};

describe('offering availability', () => {
  it.each([
    ['2026-11-19T00:59:59Z', false],
    ['2026-11-19T01:00:00Z', true],
    ['2026-11-19T01:30:00Z', true],
    ['2026-11-19T01:30:01Z', false],
  ])('compares effective window boundaries at %s independently of soft quota', (instant, open) => {
    expect(isOfferingOpen(offering, Date.parse(instant))).toBe(open);
  });

  it('excludes disabled offerings within their window', () => {
    expect(
      isOfferingOpen({ ...offering, is_enabled: false }, Date.parse(offering.enroll_start)),
    ).toBe(false);
  });
});
