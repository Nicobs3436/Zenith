import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// Borrador de la sesion activa para recuperarla si la app se cierra o el sistema la mata.
// Nativo: expo-secure-store (cifrado). Web: localStorage, mismo fallback que los tokens.
// No se anaden dependencias: SecureStore puede rechazar valores > 2048 bytes, asi que el JSON
// se trocea en fragmentos de como maximo CHUNK_SIZE caracteres (<= 3 bytes UTF-8 cada uno).

const COUNT_KEY = 'zenith_workout_draft_count';
const CHUNK_KEY_PREFIX = 'zenith_workout_draft_';
const CHUNK_SIZE = 600;
const MAX_CHUNKS = 200;
export const DRAFT_MAX_AGE_MS = 24 * 60 * 60 * 1000;

export type WorkoutDraft<Row> = {
  version: 1;
  routineId: string;
  startedAt: string;
  timezone: string;
  restEndsAt: number | null;
  rows: Row[];
  savedAt: number;
};

export function splitIntoChunks(value: string, size = CHUNK_SIZE): string[] {
  const chunks: string[] = [];
  for (let index = 0; index < value.length; index += size) {
    chunks.push(value.slice(index, index + size));
  }
  return chunks.length > 0 ? chunks : [''];
}

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

async function setItem(key: string, value: string) {
  if (Platform.OS === 'web') {
    localStorage.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function getItem(key: string) {
  if (Platform.OS === 'web') {
    return localStorage.getItem(key);
  }
  return SecureStore.getItemAsync(key);
}

async function removeItem(key: string) {
  if (Platform.OS === 'web') {
    localStorage.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

async function storedChunkCount() {
  const raw = await getItem(COUNT_KEY);
  const count = raw === null ? 0 : Number(raw);
  return Number.isInteger(count) && count > 0 ? Math.min(count, MAX_CHUNKS) : 0;
}

export async function saveWorkoutDraft<Row>(draft: WorkoutDraft<Row>) {
  const chunks = splitIntoChunks(JSON.stringify(draft));
  if (chunks.length > MAX_CHUNKS) {
    return;
  }
  const previousCount = await storedChunkCount();
  for (const [index, chunk] of chunks.entries()) {
    await setItem(`${CHUNK_KEY_PREFIX}${index}`, chunk);
  }
  for (let index = chunks.length; index < previousCount; index += 1) {
    await removeItem(`${CHUNK_KEY_PREFIX}${index}`);
  }
  await setItem(COUNT_KEY, String(chunks.length));
}

export async function loadWorkoutDraft<Row>(routineId: string): Promise<WorkoutDraft<Row> | null> {
  try {
    const count = await storedChunkCount();
    if (count === 0) {
      return null;
    }
    const chunks: string[] = [];
    for (let index = 0; index < count; index += 1) {
      const chunk = await getItem(`${CHUNK_KEY_PREFIX}${index}`);
      if (chunk === null) {
        return null;
      }
      chunks.push(chunk);
    }
    const draft = JSON.parse(chunks.join('')) as WorkoutDraft<Row>;
    return isDraftUsable(draft, routineId) ? draft : null;
  } catch {
    // Almacenamiento no disponible o borrador corrupto: empezar de cero sin romper la pantalla.
    return null;
  }
}

export async function clearWorkoutDraft() {
  try {
    const count = await storedChunkCount();
    for (let index = 0; index < count; index += 1) {
      await removeItem(`${CHUNK_KEY_PREFIX}${index}`);
    }
    await removeItem(COUNT_KEY);
  } catch {
    // Sin almacenamiento disponible no hay nada que limpiar.
  }
}
