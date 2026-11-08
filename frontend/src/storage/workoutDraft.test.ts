import { beforeEach, describe, expect, it, vi } from 'vitest';

// vi.mock se eleva antes de los imports, asi que el modulo ya recibe los mocks.
import { clearWorkoutDraft, DRAFT_MAX_AGE_MS, isDraftUsable, loadWorkoutDraft, saveWorkoutDraft, splitIntoChunks, WorkoutDraft } from './workoutDraft';

const mocks = vi.hoisted(() => {
  const values = new Map<string, string>();
  const platform = { OS: 'ios' };
  const secureStore = {
    setItemAsync: vi.fn(async (key: string, value: string) => {
      if (new TextEncoder().encode(value).length > 2048) {
        throw new Error('Value too large for SecureStore');
      }
      values.set(key, value);
    }),
    getItemAsync: vi.fn(async (key: string) => values.get(key) ?? null),
    deleteItemAsync: vi.fn(async (key: string) => {
      values.delete(key);
    }),
  };
  return { values, platform, secureStore };
});

vi.mock('react-native', () => ({ Platform: mocks.platform }));
vi.mock('expo-secure-store', () => mocks.secureStore);

type Row = { key: string; reps: string; notes: string };

function draft(overrides: Partial<WorkoutDraft<Row>> = {}): WorkoutDraft<Row> {
  return {
    version: 1,
    routineId: 'routine-1',
    startedAt: '2026-07-02T10:00:00.000Z',
    timezone: 'Europe/Madrid',
    restEndsAt: null,
    rows: Array.from({ length: 40 }, (_, index) => ({ key: `row-${index}`, reps: '10', notes: 'Técnica correcta ñ' })),
    savedAt: Date.now(),
    ...overrides,
  };
}

describe('workout draft storage', () => {
  beforeEach(() => {
    mocks.values.clear();
  });

  it('splits long values into chunks', () => {
    expect(splitIntoChunks('abcdef', 4)).toEqual(['abcd', 'ef']);
    expect(splitIntoChunks('', 4)).toEqual(['']);
  });

  it('round-trips a large draft through SecureStore chunks within the size limit', async () => {
    const saved = draft();
    await saveWorkoutDraft(saved);

    expect(Number(mocks.values.get('zenith_workout_draft_count'))).toBeGreaterThan(1);
    await expect(loadWorkoutDraft<Row>('routine-1')).resolves.toEqual(saved);
  });

  it('removes leftover chunks when a smaller draft is saved and clears everything', async () => {
    await saveWorkoutDraft(draft());
    await saveWorkoutDraft(draft({ rows: [{ key: 'only', reps: '5', notes: '' }] }));

    expect(mocks.values.get('zenith_workout_draft_count')).toBe('1');
    expect(mocks.values.has('zenith_workout_draft_1')).toBe(false);

    await clearWorkoutDraft();
    expect(mocks.values.size).toBe(0);
  });

  it('ignores drafts for other routines, stale drafts and corrupt data', async () => {
    await saveWorkoutDraft(draft());
    await expect(loadWorkoutDraft<Row>('routine-2')).resolves.toBeNull();

    expect(isDraftUsable(draft({ savedAt: Date.now() - DRAFT_MAX_AGE_MS - 1 }), 'routine-1')).toBe(false);

    mocks.values.set('zenith_workout_draft_0', '{not json');
    await expect(loadWorkoutDraft<Row>('routine-1')).resolves.toBeNull();
  });
});
