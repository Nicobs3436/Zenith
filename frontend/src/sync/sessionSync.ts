import { ApiError, AuthExpiredError, createWorkoutSession } from '@/api/client';
import { FlushResult, flushPendingSessions, PendingSession } from '@/storage/sessionOutbox';

let syncInFlight: Promise<FlushResult> | null = null;

// Errores que merecen reintento mas tarde: sin red, timeout, servidor caido o limite temporal.
export function isRetryableError(error: unknown) {
  if (error instanceof ApiError) {
    return error.status >= 500 || error.status === 408 || error.status === 429;
  }
  return !(error instanceof AuthExpiredError);
}

async function sendPending(payload: PendingSession['payload']) {
  try {
    await createWorkoutSession(payload);
    return 'sent' as const;
  } catch (error) {
    if (error instanceof AuthExpiredError) {
      return 'stop' as const;
    }
    if (isRetryableError(error)) {
      return 'retry' as const;
    }
    return { rejected: error instanceof Error ? error.message : 'El servidor rechazó la sesión.' };
  }
}

export function syncPendingSessions() {
  syncInFlight ??= flushPendingSessions(sendPending).finally(() => {
    syncInFlight = null;
  });
  return syncInFlight;
}
