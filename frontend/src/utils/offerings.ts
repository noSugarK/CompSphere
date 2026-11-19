import type { Edition } from '../api/schemas';

export function isOfferingOpen(
  offering: Pick<Edition['offerings'][number], 'is_enabled' | 'enroll_start' | 'enroll_end'>,
  now = Date.now(),
): boolean {
  return (
    offering.is_enabled &&
    Date.parse(offering.enroll_start) <= now &&
    now <= Date.parse(offering.enroll_end)
  );
}
