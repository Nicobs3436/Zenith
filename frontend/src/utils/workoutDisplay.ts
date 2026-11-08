import { Exercise, Routine, RoutineExercise, WorkoutSet } from '@/api/client';

export function exerciseName(exerciseId: string, exercises: Exercise[]) {
  return exercises.find((exercise) => exercise.id === exerciseId)?.name ?? 'Ejercicio desconocido';
}

export function routineName(routineId: string | null, routines: Routine[]) {
  if (!routineId) {
    return 'Sin rutina';
  }
  return routines.find((routine) => routine.id === routineId)?.name ?? 'Rutina no disponible';
}

export function plannedRoutineExercises(routine: Routine | null | undefined) {
  const value = (routine as { exercises?: unknown } | null | undefined)?.exercises;
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is RoutineExercise => {
    if (typeof item !== 'object' || item === null) {
      return false;
    }
    const exercise = item as Partial<RoutineExercise>;
    return typeof exercise.exercise_id === 'string' && typeof exercise.position === 'number';
  });
}

export function formatPlannedExercise(exercise: RoutineExercise) {
  const pieces: string[] = [];
  if (exercise.target_sets) {
    pieces.push(`${exercise.target_sets} series`);
  }
  if (exercise.target_reps_min !== null && exercise.target_reps_max !== null) {
    pieces.push(`${exercise.target_reps_min}-${exercise.target_reps_max} reps`);
  } else if (exercise.target_reps_min !== null) {
    pieces.push(`${exercise.target_reps_min}+ reps`);
  } else if (exercise.target_reps_max !== null) {
    pieces.push(`hasta ${exercise.target_reps_max} reps`);
  }
  if (exercise.target_rpe) {
    pieces.push(`RPE ${exercise.target_rpe}`);
  }
  if (exercise.target_rir !== undefined && exercise.target_rir !== null) {
    pieces.push(`RIR ${exercise.target_rir}`);
  }
  if (exercise.rest_seconds !== undefined && exercise.rest_seconds !== null) {
    pieces.push(`${exercise.rest_seconds}s descanso`);
  }
  return pieces.length > 0 ? pieces.join(' · ') : 'Sin objetivo definido';
}

export function formatVolumeByUnit(sets: WorkoutSet[]) {
  const totals: Record<string, number> = {};
  for (const set of sets) {
    if (!set.weight_value || !set.weight_unit) {
      continue;
    }
    const weight = Number(set.weight_value);
    if (Number.isNaN(weight)) {
      continue;
    }
    totals[set.weight_unit] = (totals[set.weight_unit] ?? 0) + weight * set.reps;
  }

  const entries = Object.entries(totals);
  if (entries.length === 0) {
    return 'Sin volumen con peso';
  }
  return entries.map(([unit, total]) => `${Number(total.toFixed(2))} ${unit}`).join(' · ');
}

export function uniqueExerciseNames(sets: WorkoutSet[], exercises: Exercise[]) {
  const names = new Set(sets.map((set) => exerciseName(set.exercise_id, exercises)));
  return [...names].join(', ');
}

// "1 ejercicio planificado" / "3 ejercicios planificados".
export function countLabel(count: number, singular: string, plural: string) {
  return `${count} ${count === 1 ? singular : plural}`;
}
