import { describe, expect, it } from 'vitest';

import { secondsBetween, secondsUntil } from './sessionTimers';

describe('session timers', () => {
  it('computes elapsed time from timestamps, even after a long background pause', () => {
    const start = Date.parse('2026-07-02T10:00:00Z');

    expect(secondsBetween(start, start + 61_500)).toBe(61);
    expect(secondsBetween(start, start + 45 * 60_000)).toBe(2700);
    expect(secondsBetween(start, start - 5_000)).toBe(0);
  });

  it('computes remaining rest and never goes negative', () => {
    const now = 1_000_000;

    expect(secondsUntil(null, now)).toBe(0);
    expect(secondsUntil(now + 90_000, now)).toBe(90);
    expect(secondsUntil(now + 500, now)).toBe(1);
    expect(secondsUntil(now - 10_000, now)).toBe(0);
  });
});
