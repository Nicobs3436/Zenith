import { describe, expect, it } from 'vitest';

import { RoutineExercise, WorkoutSession } from '@/api/client';
import { progressionHintForExercise } from './progression';

function planned(overrides: Partial<RoutineExercise> = {}): RoutineExercise {
  return {
    exercise_id: 'exercise-1',
    position: 1,
    target_sets: 3,
    target_reps_min: 8,
    target_reps_max: 10,
    target_rpe: null,
    target_rir: null,
    rest_seconds: null,
    notes: null,
    ...overrides,
  };
}

function session(startedAt: string, reps: number[], weightValue = '50', rpe?: string): WorkoutSession {
  return {
    id: startedAt,
    routine_id: null,
    started_at: startedAt,
    finished_at: null,
    timezone: 'UTC',
    notes: null,
    sets: reps.map((rep, index) => ({
      exercise_id: 'exercise-1',
      set_number: index + 1,
      reps: rep,
      weight_value: weightValue,
      weight_unit: 'kg',
      rpe,
    })),
  };
}

describe('progression', () => {
  it('recommends a conservative start without previous sessions', () => {
    const result = progressionHintForExercise(planned(), []);

    expect(result.lastSummary).toBe('Sin sesiones previas.');
    expect(result.recommendation).toBe('Empieza con una carga conservadora y prioriza técnica.');
  });

  it('uses the latest matching session only', () => {
    const result = progressionHintForExercise(planned(), [
      session('2026-07-01T10:00:00Z', [5, 5], '40'),
      session('2026-07-10T10:00:00Z', [10, 11], '50'),
    ]);

    expect(result.lastSummary).toBe('Última vez: 2 series, 10-11 reps, hasta 50 kg.');
  });

  it('recommends increasing load when the top rep range is completed with manageable RPE', () => {
    const result = progressionHintForExercise(planned(), [session('2026-07-10T10:00:00Z', [10, 10], '50', '8')]);

    expect(result.recommendation).toBe('Si calentamiento y técnica van bien, prueba 52.5 kg.');
  });

  it('keeps load when the top rep range is completed with high RPE', () => {
    const result = progressionHintForExercise(planned(), [session('2026-07-10T10:00:00Z', [10, 10], '50', '9')]);

    expect(result.recommendation).toBe('Completaste el rango, pero con RPE alto: mantén peso y busca mejor control.');
  });

  it('recommends maintaining or lowering load below the minimum rep target', () => {
    const result = progressionHintForExercise(planned(), [session('2026-07-10T10:00:00Z', [6, 7], '50')]);

    expect(result.recommendation).toBe('No alcanzaste el mínimo objetivo: mantén o baja un poco el peso.');
  });

  it('handles bodyweight sets without load metrics', () => {
    const bodyweightSession = session('2026-07-10T10:00:00Z', [8, 9], '50');
    bodyweightSession.sets = bodyweightSession.sets.map((set) => ({ ...set, weight_value: null, weight_unit: null }));

    const result = progressionHintForExercise(planned(), [bodyweightSession]);

    expect(result.lastSummary).toBe('Última vez: 2 series, 8-9 reps sin peso.');
    expect(result.recommendation).toBe('Mantén reps controladas o añade carga solo si la técnica fue solida.');
  });
});
