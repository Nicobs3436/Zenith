import * as Sentry from '@sentry/react-native';

// Informes de errores (plan gratuito de Sentry). Sin EXPO_PUBLIC_SENTRY_DSN queda desactivado.
const SENSITIVE_KEY = /authorization|cookie|password|token|email/i;

type SentryLikeEvent = {
  request?: { data?: unknown; cookies?: unknown; headers?: Record<string, string>; query_string?: unknown };
  user?: Record<string, unknown>;
  breadcrumbs?: { category?: string; data?: Record<string, unknown> }[];
  extra?: Record<string, unknown>;
};

function scrub(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(scrub);
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, SENSITIVE_KEY.test(key) ? '[Filtered]' : scrub(item)]),
    );
  }
  return value;
}

// Nunca enviar cuerpos de peticiones (datos de entrenamiento y salud), credenciales ni datos personales.
export function scrubEvent<T extends SentryLikeEvent>(event: T): T {
  if (event.request) {
    delete event.request.data;
    delete event.request.cookies;
    delete event.request.query_string;
    if (event.request.headers) {
      event.request.headers = scrub(event.request.headers) as Record<string, string>;
    }
  }
  if (event.user) {
    event.user = event.user.id ? { id: event.user.id } : {};
  }
  if (event.breadcrumbs) {
    event.breadcrumbs = event.breadcrumbs.map((crumb) =>
      crumb.category === 'fetch' || crumb.category === 'xhr'
        ? { ...crumb, data: crumb.data ? { method: crumb.data.method, status_code: crumb.data.status_code } : undefined }
        : { ...crumb, data: crumb.data ? (scrub(crumb.data) as Record<string, unknown>) : undefined },
    );
  }
  if (event.extra) {
    event.extra = scrub(event.extra) as Record<string, unknown>;
  }
  return event;
}

let initialized = false;

export function initSentry(dsn = process.env.EXPO_PUBLIC_SENTRY_DSN) {
  if (initialized || !dsn) {
    return false;
  }
  Sentry.init({
    dsn,
    sendDefaultPii: false,
    tracesSampleRate: 0,
    environment: process.env.NODE_ENV,
    beforeSend: (event) => scrubEvent(event as SentryLikeEvent) as typeof event,
    beforeBreadcrumb: (breadcrumb) => scrubEvent({ breadcrumbs: [breadcrumb as never] }).breadcrumbs?.[0] as typeof breadcrumb,
  });
  initialized = true;
  return true;
}
