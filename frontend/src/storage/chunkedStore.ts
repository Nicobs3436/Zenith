import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// Guarda JSON de cualquier tamano en el dispositivo.
// Nativo: expo-secure-store (cifrado), que puede rechazar valores > 2048 bytes, asi que el JSON se
// trocea en fragmentos de CHUNK_SIZE caracteres (<= 3 bytes UTF-8 cada uno). Web: localStorage.
// Sin dependencias nuevas.

const CHUNK_SIZE = 600;
const MAX_CHUNKS = 400;

export function splitIntoChunks(value: string, size = CHUNK_SIZE): string[] {
  const chunks: string[] = [];
  for (let index = 0; index < value.length; index += size) {
    chunks.push(value.slice(index, index + size));
  }
  return chunks.length > 0 ? chunks : [''];
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

const countKey = (prefix: string) => `${prefix}_count`;
const chunkKey = (prefix: string, index: number) => `${prefix}_${index}`;

async function storedChunkCount(prefix: string) {
  const raw = await getItem(countKey(prefix));
  const count = raw === null ? 0 : Number(raw);
  return Number.isInteger(count) && count > 0 ? Math.min(count, MAX_CHUNKS) : 0;
}

export async function saveJson(prefix: string, value: unknown) {
  const chunks = splitIntoChunks(JSON.stringify(value));
  if (chunks.length > MAX_CHUNKS) {
    throw new Error('Los datos son demasiado grandes para guardarlos en el dispositivo.');
  }
  const previousCount = await storedChunkCount(prefix);
  for (const [index, chunk] of chunks.entries()) {
    await setItem(chunkKey(prefix, index), chunk);
  }
  for (let index = chunks.length; index < previousCount; index += 1) {
    await removeItem(chunkKey(prefix, index));
  }
  await setItem(countKey(prefix), String(chunks.length));
}

export async function loadJson<T>(prefix: string): Promise<T | null> {
  try {
    const count = await storedChunkCount(prefix);
    if (count === 0) {
      return null;
    }
    const chunks: string[] = [];
    for (let index = 0; index < count; index += 1) {
      const chunk = await getItem(chunkKey(prefix, index));
      if (chunk === null) {
        return null;
      }
      chunks.push(chunk);
    }
    return JSON.parse(chunks.join('')) as T;
  } catch {
    // Almacenamiento no disponible o datos corruptos: se trata como vacio sin romper la pantalla.
    return null;
  }
}

export async function clearJson(prefix: string) {
  try {
    const count = await storedChunkCount(prefix);
    for (let index = 0; index < count; index += 1) {
      await removeItem(chunkKey(prefix, index));
    }
    await removeItem(countKey(prefix));
  } catch {
    // Sin almacenamiento disponible no hay nada que limpiar.
  }
}
