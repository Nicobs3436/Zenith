import { describe, expect, it } from 'vitest';

import { RoutineExercise } from '@/api/client';
import { buildRoutineExercises, newRoutineExerciseRow, RoutineExerciseRow, routineExerciseToRow } from './routineForm';

function row(overrides: Partial<RoutineExerciseRow> = {}): RoutineExerciseRow {
  return {
    key: 'row-1',
    exercise_id: 'exercise-1',
    target_sets: '3',
    target_reps_min: '8',
    target_reps_max: '12',
    target_weight_value: '',
    target_weight_unit: 'kg',
    target_rpe: '',
    target_rir: '',
    rest_seconds: '',
    notes: '',
    ...overrides,
  };
}

describe('routineForm', () => {
  it('creates a default routine exercise row', () => {
    const result = newRoutineExerciseRow('exercise-1');

    expect(result.exercise_id).toBe('exercise-1');
    expect(result.target_sets).toBe('3');
    expect(result.target_reps_min).toBe('8');
    expect(result.target_reps_max).toBe('12');
    expect(result.key).toBeTruthy();
  });

  it('converts an API routine exercise to an editable row', () => {
    const exercise: RoutineExercise = {
      id: 'routine-exercise-1',
      exercise_id: 'exercise-1',
      position: 1,
      target_sets: 4,
      target_reps_min: 6,
      target_reps_max: 10,
      target_weight_value: '50.00',
      target_weight_unit: 'kg',
      target_rpe: '8',
      target_rir: 2,
      rest_seconds: 120,
      notes: 'Mantener control',
    };

    expect(routineExerciseToRow(exercise)).toEqual({
      key: 'routine-exercise-1',
      exercise_id: 'exercise-1',
      target_sets: '4',
      target_reps_min: '6',
      target_reps_max: '10',
      target_weight_value: '50.00',
      target_weight_unit: 'kg',
      target_rpe: '8',
      target_rir: '2',
      rest_seconds: '120',
      notes: 'Mantener control',
    });
  });

  it('builds routine exercises with positions and trimmed optional values', () => {
    const result = buildRoutineExercises([
      row({ target_weight_value: ' 50 ', target_weight_unit: 'kg', target_rpe: ' 8 ', target_rir: '2', rest_seconds: '90', notes: ' Pausa abajo ' }),
      row({ key: 'row-2', exercise_id: 'exercise-2', target_sets: '', target_reps_min: '', target_reps_max: '' }),
    ]);

    expect(result.error).toBeNull();
    expect(result.exercises).toEqual([
      {
        exercise_id: 'exercise-1',
        position: 1,
        target_sets: 3,
        target_reps_min: 8,
        target_reps_max: 12,
        target_weight_value: '50',
        target_weight_unit: 'kg',
        target_rpe: '8',
        target_rir: 2,
        rest_seconds: 90,
        notes: 'Pausa abajo',
      },
      {
        exercise_id: 'exercise-2',
        position: 2,
        target_sets: null,
        target_reps_min: null,
        target_reps_max: null,
      },
    ]);
  });

  it('requires at least one exercise', () => {
    const result = buildRoutineExercises([]);

    expect(result.exercises).toBeNull();
    expect(result.error).toBe('Necesitas al menos un ejercicio en la rutina.');
  });

  it('rejects invalid rep ranges', () => {
    const result = buildRoutineExercises([row({ target_reps_min: '12', target_reps_max: '8' })]);

    expect(result.exercises).toBeNull();
    expect(result.error).toBe('Las reps max del ejercicio 1 deben ser mayores o iguales a reps min.');
  });

  it('rejects invalid RPE', () => {
    const result = buildRoutineExercises([row({ target_rpe: '0' })]);

    expect(result.exercises).toBeNull();
    expect(result.error).toBe('El RPE objetivo del ejercicio 1 no es válido.');
  });
});
