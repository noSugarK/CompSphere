import { describe, expect, it } from 'vitest';
import { formatEventDateTime } from '../src/utils/format';

describe('event timestamps', () => {
  it('renders an instant in Shanghai across the UTC date boundary', () => {
    expect(formatEventDateTime('2026-11-18T16:05:00Z')).toBe('2026-11-19 00:05');
  });
  it('keeps equivalent offset timestamps identical', () => {
    expect(formatEventDateTime('2026-11-19T00:05:00+08:00')).toBe(
      formatEventDateTime('2026-11-18T16:05:00Z'),
    );
  });
});
