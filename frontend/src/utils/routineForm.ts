import { RoutineExercise } from '@/api/client';
import { normalizeDecimalInput } from '@/utils/sessionForm';

export type RoutineExerciseRow = {
  key: string;
  exercise_id: string;
  target_sets: string;
  target_reps_min: string;
  target_reps_max: string;
  target_weight_value: string;
  target_weight_unit: 'kg' | 'lb';
  target_rpe: string;
  target_rir: string;
  rest_seconds: string;
  notes: string;
};

export type BuildRoutineExercisesResult =
  | { exercises: RoutineExercise[]; error: null }
  | { exercises: null; error: string };

export function newRoutineExerciseRow(exerciseId: string): RoutineExerciseRow {
  return {
    key: `${Date.now()}-${Math.random()}`,
    exercise_id: exerciseId,
    target_sets: '3',
    target_reps_min: '8',
    target_reps_max: '12',
    target_weight_value: '',
    target_weight_unit: 'kg',
    target_rpe: '',
    target_rir: '',
    rest_seconds: '',
    notes: '',
  };
}

export function routineExerciseToRow(exercise: RoutineExercise): RoutineExerciseRow {
  return {
    key: exercise.id ?? `${exercise.exercise_id}-${exercise.position}`,
    exercise_id: exercise.exercise_id,
    target_sets: exercise.target_sets?.toString() ?? '',
    target_reps_min: exercise.target_reps_min?.toString() ?? '',
    target_reps_max: exercise.target_reps_max?.toString() ?? '',
    target_weight_value: exercise.target_weight_value ?? '',
    target_weight_unit: exercise.target_weight_unit ?? 'kg',
    target_rpe: exercise.target_rpe ?? '',
    target_rir: exercise.target_rir?.toString() ?? '',
    rest_seconds: exercise.rest_seconds?.toString() ?? '',
    notes: exercise.notes ?? '',
  };
}

function parseOptionalNumber(value: string, label: string, min: number, max?: number) {
  const trimmed = normalizeDecimalInput(value);
  if (!trimmed) {
    return { value: null, error: null };
  }
  const parsed = Number(trimmed);
  if (Number.isNaN(parsed) || parsed < min || (max !== undefined && parsed > max)) {
    return { value: null, error: `${label} no es valido.` };
  }
  return { value: parsed, error: null };
}

function parseOptionalInteger(value: string, label: string, min: number) {
  const trimmed = value.trim();
  if (!trimmed) {
    return { value: null, error: null };
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < min) {
    return { value: null, error: `${label} no es valido.` };
  }
  return { value: parsed, error: null };
}

export function buildRoutineExercises(rows: RoutineExerciseRow[]): BuildRoutineExercisesResult {
  if (rows.length === 0) {
    return { exercises: null, error: 'Necesitas al menos un ejercicio en la rutina.' };
  }

  const exercises: RoutineExercise[] = [];
  for (const [index, row] of rows.entries()) {
    if (!row.exercise_id) {
      return { exercises: null, error: `El ejercicio ${index + 1} necesita una seleccion.` };
    }

    const targetSets = parseOptionalInteger(row.target_sets, `Las series del ejercicio ${index + 1}`, 1);
    if (targetSets.error) {
      return { exercises: null, error: targetSets.error };
    }

    const targetRepsMin = parseOptionalInteger(row.target_reps_min, `Las reps min del ejercicio ${index + 1}`, 0);
    if (targetRepsMin.error) {
      return { exercises: null, error: targetRepsMin.error };
    }

    const targetRepsMax = parseOptionalInteger(row.target_reps_max, `Las reps max del ejercicio ${index + 1}`, 0);
    if (targetRepsMax.error) {
      return { exercises: null, error: targetRepsMax.error };
    }

    if (targetRepsMin.value !== null && targetRepsMax.value !== null && targetRepsMax.value < targetRepsMin.value) {
      return { exercises: null, error: `Las reps max del ejercicio ${index + 1} deben ser mayores o iguales a reps min.` };
    }

    const targetRpe = parseOptionalNumber(row.target_rpe, `El RPE objetivo del ejercicio ${index + 1}`, 1, 10);
    if (targetRpe.error) {
      return { exercises: null, error: targetRpe.error };
    }

    const targetWeight = parseOptionalNumber(row.target_weight_value, `El peso objetivo del ejercicio ${index + 1}`, 0, 2500);
    if (targetWeight.error) {
      return { exercises: null, error: targetWeight.error };
    }

    const targetRir = parseOptionalInteger(row.target_rir, `El RIR objetivo del ejercicio ${index + 1}`, 0);
    if (targetRir.error) {
      return { exercises: null, error: targetRir.error };
    }

    const restSeconds = parseOptionalInteger(row.rest_seconds, `El descanso del ejercicio ${index + 1}`, 0);
    if (restSeconds.error) {
      return { exercises: null, error: restSeconds.error };
    }

    exercises.push({
      exercise_id: row.exercise_id,
      position: index + 1,
      target_sets: targetSets.value,
      target_reps_min: targetRepsMin.value,
      target_reps_max: targetRepsMax.value,
      ...(targetWeight.value !== null
        ? { target_weight_value: normalizeDecimalInput(row.target_weight_value), target_weight_unit: row.target_weight_unit }
        : {}),
      ...(targetRpe.value !== null ? { target_rpe: normalizeDecimalInput(row.target_rpe) } : {}),
      ...(targetRir.value !== null ? { target_rir: targetRir.value } : {}),
      ...(restSeconds.value !== null ? { rest_seconds: restSeconds.value } : {}),
      ...(row.notes.trim() ? { notes: row.notes.trim() } : {}),
    });
  }

  return { exercises, error: null };
}
