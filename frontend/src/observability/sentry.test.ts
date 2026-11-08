import { describe, expect, it, vi } from 'vitest';

// vi.mock se eleva antes de los imports, asi que el modulo ya recibe los mocks.
import { initSentry, scrubEvent } from './sentry';

const sentry = vi.hoisted(() => ({ init: vi.fn() }));
vi.mock('@sentry/react-native', () => sentry);

describe('sentry', () => {
  it('stays disabled without a DSN', () => {
    expect(initSentry('')).toBe(false);
    expect(sentry.init).not.toHaveBeenCalled();
  });

  it('removes bodies, credentials and personal data from events', () => {
    const event = scrubEvent({
      request: { data: { weight_kg: 80 }, cookies: { a: 'b' }, query_string: 'token=x', headers: { Authorization: 'Bearer x', Accept: 'json' } },
      user: { id: 'u1', email: 'a@b.com', ip_address: '1.2.3.4' },
      breadcrumbs: [{ category: 'fetch', data: { method: 'POST', status_code: 500, url: '/auth/login', body: '{"password":"x"}' } }],
      extra: { password: 'secret', screen: 'stats' },
    });

    expect(event.request).toEqual({ headers: { Authorization: '[Filtered]', Accept: 'json' } });
    expect(event.user).toEqual({ id: 'u1' });
    expect(event.breadcrumbs?.[0].data).toEqual({ method: 'POST', status_code: 500 });
    expect(event.extra).toEqual({ password: '[Filtered]', screen: 'stats' });
  });
});
