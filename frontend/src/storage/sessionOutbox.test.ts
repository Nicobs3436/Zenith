import { beforeEach, describe, expect, it, vi } from 'vitest';

// vi.mock se eleva antes de los imports, asi que el modulo ya recibe los mocks.
import { enqueueSession, flushPendingSessions, listPendingSessions, newClientRequestId } from './sessionOutbox';

const mocks = vi.hoisted(() => {
  const values = new Map<string, string>();
  return {
    values,
    platform: { OS: 'ios' },
    secureStore: {
      setItemAsync: vi.fn(async (key: string, value: string) => {
        values.set(key, value);
      }),
      getItemAsync: vi.fn(async (key: string) => values.get(key) ?? null),
      deleteItemAsync: vi.fn(async (key: string) => {
        values.delete(key);
      }),
    },
  };
});

vi.mock('react-native', () => ({ Platform: mocks.platform }));
vi.mock('expo-secure-store', () => mocks.secureStore);

function payload(id: string) {
  return { client_request_id: id, started_at: '2026-07-02T10:00:00.000Z', timezone: 'Europe/Madrid', sets: [] };
}

describe('session outbox', () => {
  beforeEach(() => {
    mocks.values.clear();
  });

  it('queues sessions once per client request id', async () => {
    await enqueueSession(payload('a'), 'Pierna');
    await enqueueSession(payload('a'), 'Pierna');
    await enqueueSession(payload('b'), 'Torso');

    expect((await listPendingSessions()).map((item) => item.payload.client_request_id)).toEqual(['a', 'b']);
  });

  it('removes sent sessions, keeps retryable ones and flags rejected ones', async () => {
    await enqueueSession(payload('sent'), 'A');
    await enqueueSession(payload('retry'), 'B');
    await enqueueSession(payload('bad'), 'C');

    const result = await flushPendingSessions(async (item) => {
      if (item.client_request_id === 'sent') return 'sent';
      if (item.client_request_id === 'retry') return 'retry';
      return { rejected: 'Datos no válidos' };
    });

    expect(result).toEqual({ sent: 1, pending: 1, rejected: 1 });
    const remaining = await listPendingSessions();
    expect(remaining.map((item) => [item.payload.client_request_id, item.attempts, item.rejected ?? null])).toEqual([
      ['retry', 1, null],
      ['bad', 1, 'Datos no válidos'],
    ]);
  });

  it('stops at an expired session and keeps everything after it', async () => {
    await enqueueSession(payload('first'), 'A');
    await enqueueSession(payload('second'), 'B');
    const send = vi.fn(async () => 'stop' as const);

    const result = await flushPendingSessions(send);

    expect(send).toHaveBeenCalledOnce();
    expect(result).toEqual({ sent: 0, pending: 2, rejected: 0 });
  });

  it('generates RFC 4122 v4 ids', () => {
    const id = newClientRequestId();
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(newClientRequestId()).not.toBe(id);
  });
});
