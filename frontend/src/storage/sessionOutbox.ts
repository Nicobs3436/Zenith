import type { WorkoutSessionPayload } from '@/api/client';
import { clearJson, loadJson, saveJson } from '@/storage/chunkedStore';

// Cola de sesiones terminadas sin conexion. Cada una lleva client_request_id: reenviarla varias
// veces no la duplica en el servidor.

const OUTBOX_PREFIX = 'zenith_session_outbox';

export type PendingSession = {
  payload: WorkoutSessionPayload & { client_request_id: string };
  label: string;
  queuedAt: number;
  attempts: number;
  // Rechazada por el servidor (datos no validos): se conserva para no perderla y se muestra al usuario.
  rejected?: string;
};

export type FlushResult = { sent: number; pending: number; rejected: number };

export async function listPendingSessions(): Promise<PendingSession[]> {
  const items = await loadJson<PendingSession[]>(OUTBOX_PREFIX);
  return Array.isArray(items) ? items : [];
}

async function savePendingSessions(items: PendingSession[]) {
  if (items.length === 0) {
    await clearJson(OUTBOX_PREFIX);
    return;
  }
  await saveJson(OUTBOX_PREFIX, items);
}

export async function enqueueSession(payload: PendingSession['payload'], label: string) {
  const items = await listPendingSessions();
  if (items.some((item) => item.payload.client_request_id === payload.client_request_id)) {
    return;
  }
  await savePendingSessions([...items, { payload, label, queuedAt: Date.now(), attempts: 0 }]);
}

export async function discardPendingSession(clientRequestId: string) {
  const items = await listPendingSessions();
  await savePendingSessions(items.filter((item) => item.payload.client_request_id !== clientRequestId));
}

type SendOutcome = 'sent' | 'retry' | { rejected: string } | 'stop';

// `send` decide como clasificar cada error (red -> retry, 4xx -> rejected, sesion caducada -> stop).
export async function flushPendingSessions(send: (payload: PendingSession['payload']) => Promise<SendOutcome>): Promise<FlushResult> {
  const items = await listPendingSessions();
  const remaining: PendingSession[] = [];
  let sent = 0;
  let stopped = false;

  for (const item of items) {
    if (stopped || item.rejected) {
      remaining.push(item);
      continue;
    }
    const outcome = await send(item.payload);
    if (outcome === 'sent') {
      sent += 1;
    } else if (outcome === 'stop') {
      stopped = true;
      remaining.push(item);
    } else if (outcome === 'retry') {
      remaining.push({ ...item, attempts: item.attempts + 1 });
    } else {
      remaining.push({ ...item, attempts: item.attempts + 1, rejected: outcome.rejected });
    }
  }

  await savePendingSessions(remaining);
  return {
    sent,
    pending: remaining.filter((item) => !item.rejected).length,
    rejected: remaining.filter((item) => item.rejected).length,
  };
}

// UUID v4 para idempotencia. Usa crypto si existe; si no, Math.random basta para no colisionar por usuario.
export function newClientRequestId() {
  const cryptoApi = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (cryptoApi?.randomUUID) {
    return cryptoApi.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    return (char === 'x' ? random : (random % 4) + 8).toString(16);
  });
}
