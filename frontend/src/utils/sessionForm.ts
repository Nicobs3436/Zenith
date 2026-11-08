import { Routine, WorkoutSet } from '@/api/client';

export type WeightUnit = 'kg' | 'lb';

export type SetRow = {
  key: string;
  exercise_id: string;
  reps: string;
  weight_value: string;
  weight_unit: WeightUnit;
  rpe: string;
  rir: string;
  rest_seconds: string;
  notes: string;
};

export type BuildSetsResult =
  | { sets: WorkoutSet[]; error: null }
  | { sets: null; error: string };

export function newSetRow(exerciseId: string): SetRow {
  return {
    key: `${Date.now()}-${Math.random()}`,
    exercise_id: exerciseId,
    reps: '10',
    weight_value: '',
    weight_unit: 'kg',
    rpe: '',
    rir: '',
    rest_seconds: '',
    notes: '',
  };
}

export function duplicateSetRow(row: SetRow): SetRow {
  return { ...row, key: `${Date.now()}-${Math.random()}` };
}

export function rowsFromRoutine(routine: Routine): SetRow[] {
  return [...routine.exercises]
    .sort((left, right) => left.position - right.position)
    .flatMap((exercise) => {
      const setCount = Math.max(1, exercise.target_sets ?? 1);
      return Array.from({ length: setCount }, () => ({
        ...newSetRow(exercise.exercise_id),
        reps: exercise.target_reps_min?.toString() ?? '10',
        rpe: exercise.target_rpe ?? '',
        rir: exercise.target_rir?.toString() ?? '',
        rest_seconds: exercise.rest_seconds?.toString() ?? '',
        notes: exercise.notes ?? '',
      }));
    });
}

// Acepta coma decimal (teclados en espanol): "62,5" -> 62.5.
export function normalizeDecimalInput(value: string) {
  return value.trim().replace(',', '.');
}

// Fecha legible en hora local del dispositivo: "2026-07-02 10:05". Es lo que el usuario edita.
export function formatLocalDateTime(value: Date | string) {
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const pad = (part: number) => part.toString().padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// Convierte la fecha escrita por el usuario a ISO con zona. Sin offset se interpreta como hora local
// del dispositivo (lo que el usuario ve), nunca como UTC silencioso. Devuelve null si no es valida.
export function toIsoDateTime(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = new Date(trimmed.includes('T') || !trimmed.includes(' ') ? trimmed : trimmed.replace(' ', 'T'));
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

// Mismos topes que el backend (backend/app/domain/routines.py).
const MAX_WEIGHT = 2500;
const MAX_REPS = 1000;

function parseOptionalNumber(value: string, label: string, min: number, max?: number) {
  const trimmed = normalizeDecimalInput(value);
  if (!trimmed) {
    return { value: null, error: null };
  }
  const parsed = Number(trimmed);
  if (Number.isNaN(parsed) || parsed < min || (max !== undefined && parsed > max)) {
    return { value: null, error: `${label} no es válido.` };
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
    return { value: null, error: `${label} no es válido.` };
  }
  return { value: parsed, error: null };
}

export function buildWorkoutSets(rows: SetRow[]): BuildSetsResult {
  const sets: WorkoutSet[] = [];

  for (const [index, row] of rows.entries()) {
    if (!row.exercise_id) {
      return { sets: null, error: `La serie ${index + 1} necesita ejercicio.` };
    }

    const reps = Number(row.reps.trim());
    if (!Number.isInteger(reps) || reps < 0 || reps > MAX_REPS) {
      return { sets: null, error: `Las reps de la serie ${index + 1} no son válidas.` };
    }

    const weight = parseOptionalNumber(row.weight_value, `El peso de la serie ${index + 1}`, 0, MAX_WEIGHT);
    if (weight.error) {
      return { sets: null, error: weight.error };
    }

    const rpe = parseOptionalNumber(row.rpe, `El RPE de la serie ${index + 1}`, 1, 10);
    if (rpe.error) {
      return { sets: null, error: rpe.error };
    }

    const rir = parseOptionalInteger(row.rir, `El RIR de la serie ${index + 1}`, 0);
    if (rir.error) {
      return { sets: null, error: rir.error };
    }

    const restSeconds = parseOptionalInteger(row.rest_seconds, `El descanso de la serie ${index + 1}`, 0);
    if (restSeconds.error) {
      return { sets: null, error: restSeconds.error };
    }

    sets.push({
      exercise_id: row.exercise_id,
      set_number: index + 1,
      reps,
      ...(weight.value !== null ? { weight_value: normalizeDecimalInput(row.weight_value), weight_unit: row.weight_unit } : {}),
      ...(rpe.value !== null ? { rpe: normalizeDecimalInput(row.rpe) } : {}),
      ...(rir.value !== null ? { rir: rir.value } : {}),
      ...(restSeconds.value !== null ? { rest_seconds: restSeconds.value } : {}),
      ...(row.notes.trim() ? { notes: row.notes.trim() } : {}),
    });
  }

  return { sets, error: null };
}
