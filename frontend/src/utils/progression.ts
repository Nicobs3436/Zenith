import { RoutineExercise, WorkoutSession, WorkoutSet } from '@/api/client';

export type ProgressionHint = {
  lastSummary: string;
  recommendation: string;
};

function numberOrNull(value: string | null | undefined) {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function average(values: number[]) {
  if (values.length === 0) {
    return null;
  }
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function latestSetsForExercise(exerciseId: string, sessions: WorkoutSession[]): WorkoutSet[] {
  const latestSession = [...sessions]
    .filter((session) => session.sets.some((set) => set.exercise_id === exerciseId))
    .sort((left, right) => new Date(right.started_at).getTime() - new Date(left.started_at).getTime())[0];

  return latestSession?.sets.filter((set) => set.exercise_id === exerciseId) ?? [];
}

export function progressionHintForExercise(planned: RoutineExercise, sessions: WorkoutSession[]): ProgressionHint {
  const lastSets = latestSetsForExercise(planned.exercise_id, sessions);
  if (lastSets.length === 0) {
    return {
      lastSummary: 'Sin sesiones previas.',
      recommendation: 'Empieza con una carga conservadora y prioriza técnica.',
    };
  }

  const reps = lastSets.map((set) => set.reps);
  const weightedSets = lastSets.filter((set) => set.weight_value && set.weight_unit);
  const heaviestSet = weightedSets
    .map((set) => ({ set, weight: numberOrNull(set.weight_value) ?? 0 }))
    .sort((left, right) => right.weight - left.weight)[0]?.set;
  const rpeAverage = average(lastSets.map((set) => numberOrNull(set.rpe)).filter((value): value is number => value !== null));
  const minReps = Math.min(...reps);
  const maxReps = Math.max(...reps);
  const lastSummary = heaviestSet
    ? `Última vez: ${lastSets.length} series, ${minReps}-${maxReps} reps, hasta ${heaviestSet.weight_value} ${heaviestSet.weight_unit}.`
    : `Última vez: ${lastSets.length} series, ${minReps}-${maxReps} reps sin peso.`;

  if (!heaviestSet || !heaviestSet.weight_value || !heaviestSet.weight_unit) {
    return { lastSummary, recommendation: 'Mantén reps controladas o añade carga solo si la técnica fue solida.' };
  }

  if (planned.target_reps_max !== null && minReps >= planned.target_reps_max) {
    if (rpeAverage !== null && rpeAverage >= 9) {
      return { lastSummary, recommendation: 'Completaste el rango, pero con RPE alto: mantén peso y busca mejor control.' };
    }
    const increment = heaviestSet.weight_unit === 'kg' ? 2.5 : 5;
    const nextWeight = Number(heaviestSet.weight_value) + increment;
    return { lastSummary, recommendation: `Si calentamiento y técnica van bien, prueba ${nextWeight} ${heaviestSet.weight_unit}.` };
  }

  if (planned.target_reps_min !== null && minReps < planned.target_reps_min) {
    return { lastSummary, recommendation: 'No alcanzaste el mínimo objetivo: mantén o baja un poco el peso.' };
  }

  return { lastSummary, recommendation: 'Mantén el peso e intenta acercarte al rango alto de reps.' };
}
