import { describe, expect, it } from 'vitest';

import { Routine } from '@/api/client';
import { buildWorkoutSets, duplicateSetRow, newSetRow, rowsFromRoutine, SetRow } from './sessionForm';

function row(overrides: Partial<SetRow> = {}): SetRow {
  return {
    key: 'row-1',
    exercise_id: 'exercise-1',
    reps: '10',
    weight_value: '',
    weight_unit: 'kg',
    rpe: '',
    rir: '',
    rest_seconds: '',
    notes: '',
    ...overrides,
  };
}

describe('sessionForm', () => {
  it('creates a default set row', () => {
    const result = newSetRow('exercise-1');

    expect(result.exercise_id).toBe('exercise-1');
    expect(result.reps).toBe('10');
    expect(result.weight_unit).toBe('kg');
    expect(result.key).toBeTruthy();
  });

  it('duplicates a row with a new key and same values', () => {
    const original = row({ key: 'original', reps: '8', weight_value: '50' });
    const duplicate = duplicateSetRow(original);

    expect(duplicate).toMatchObject({ reps: '8', weight_value: '50', exercise_id: 'exercise-1' });
    expect(duplicate.key).not.toBe(original.key);
  });

  it('builds rows from a routine sorted by planned position', () => {
    const routine = {
      id: 'routine-1',
      name: 'Rutina',
      goal: null,
      description: null,
      exercises: [
        { exercise_id: 'second', position: 2, target_sets: 1, target_reps_min: 6, target_reps_max: 8, target_rpe: '8', target_rir: 2, rest_seconds: 120, notes: 'Pesado' },
        { exercise_id: 'first', position: 1, target_sets: 2, target_reps_min: 10, target_reps_max: 12, target_rpe: null, target_rir: null, rest_seconds: null, notes: null },
      ],
    } satisfies Routine;

    const result = rowsFromRoutine(routine);

    expect(result.map((item) => item.exercise_id)).toEqual(['first', 'first', 'second']);
    expect(result[2]).toMatchObject({ reps: '6', rpe: '8', rir: '2', rest_seconds: '120', notes: 'Pesado' });
  });

  it('builds workout sets with optional values only when present', () => {
    const result = buildWorkoutSets([
      row({ reps: ' 8 ', weight_value: ' 50 ', weight_unit: 'kg', rpe: '8.5', rir: '2', rest_seconds: '90', notes: ' Buena serie ' }),
      row({ key: 'row-2', reps: '12', weight_value: '', rpe: '', rir: '', rest_seconds: '', notes: '' }),
    ]);

    expect(result.error).toBeNull();
    expect(result.sets).toEqual([
      {
        exercise_id: 'exercise-1',
        set_number: 1,
        reps: 8,
        weight_value: '50',
        weight_unit: 'kg',
        rpe: '8.5',
        rir: 2,
        rest_seconds: 90,
        notes: 'Buena serie',
      },
      {
        exercise_id: 'exercise-1',
        set_number: 2,
        reps: 12,
      },
    ]);
  });

  it('returns a readable error for invalid reps', () => {
    const result = buildWorkoutSets([row({ reps: '8.5' })]);

    expect(result.sets).toBeNull();
    expect(result.error).toBe('Las reps de la serie 1 no son validas.');
  });

  it('rejects unrealistic weight and reps', () => {
    expect(buildWorkoutSets([row({ weight_value: '100000' })]).error).toBe('El peso de la serie 1 no es valido.');
    expect(buildWorkoutSets([row({ reps: '5000' })]).error).toBe('Las reps de la serie 1 no son validas.');
  });

  it('returns a readable error for invalid RPE', () => {
    const result = buildWorkoutSets([row({ rpe: '11' })]);

    expect(result.sets).toBeNull();
    expect(result.error).toBe('El RPE de la serie 1 no es valido.');
  });
});
