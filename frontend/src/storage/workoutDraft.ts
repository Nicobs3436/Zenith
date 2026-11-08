import { clearJson, loadJson, saveJson } from '@/storage/chunkedStore';

// Borrador de la sesion activa para recuperarla si la app se cierra o el sistema la mata.
// Se borra al finalizar/cancelar o cuando tiene mas de 24 h.

export { splitIntoChunks } from '@/storage/chunkedStore';

const DRAFT_PREFIX = 'zenith_workout_draft';
export const DRAFT_MAX_AGE_MS = 24 * 60 * 60 * 1000;

export type WorkoutDraft<Row> = {
  version: 1;
  routineId: string;
  startedAt: string;
  timezone: string;
  restEndsAt: number | null;
  rows: Row[];
  savedAt: number;
  // Id de idempotencia de la sesion: se mantiene entre reintentos para no duplicarla.
  clientRequestId?: string;
};

export function isDraftUsable<Row>(draft: WorkoutDraft<Row> | null, routineId: string, now = Date.now()): draft is WorkoutDraft<Row> {
  return (
    draft !== null &&
    draft.version === 1 &&
    draft.routineId === routineId &&
    Array.isArray(draft.rows) &&
    draft.rows.length > 0 &&
    now - draft.savedAt <= DRAFT_MAX_AGE_MS
  );
}

export async function saveWorkoutDraft<Row>(draft: WorkoutDraft<Row>) {
  try {
    await saveJson(DRAFT_PREFIX, draft);
  } catch {
    // Un borrador enorme o un almacenamiento lleno no debe interrumpir el entrenamiento.
  }
}

export async function loadWorkoutDraft<Row>(routineId: string): Promise<WorkoutDraft<Row> | null> {
  const draft = await loadJson<WorkoutDraft<Row>>(DRAFT_PREFIX);
  return isDraftUsable(draft, routineId) ? draft : null;
}

export async function clearWorkoutDraft() {
  await clearJson(DRAFT_PREFIX);
}
