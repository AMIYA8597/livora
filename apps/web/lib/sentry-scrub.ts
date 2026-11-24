/**
 * What a browser or server error report may contain: no cookies, bodies, query strings, auth
 * headers or IPs, users by id only, and tokens redacted from messages. Pure (no imports), so it is
 * unit-tested and shared by the client and server Sentry setup.
 */

type Dict = Record<string, unknown>;

const DROP_HEADERS = new Set(["authorization", "cookie", "set-cookie", "x-api-key", "x-forwarded-for", "x-real-ip"]);
const PATTERNS: [RegExp, string][] = [
  [/Bearer\s+[A-Za-z0-9\-_.]+/gi, "Bearer [REDACTED]"],
  [/("(?:password|token|access_token|refresh_token|otp|code)"\s*:\s*)"[^"]*"/gi, '$1"[REDACTED]"'],
  [/([?&](?:token|access_token|refresh_token|code)=)[^&\s#]+/gi, "$1[REDACTED]"],
  [/eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+/g, "[REDACTED_JWT]"],
];

export function redact(text: string): string {
  return PATTERNS.reduce((out, [re, replacement]) => out.replace(re, replacement), text);
}

export function stripQuery(url: string): string {
  return url.split(/[?#]/, 1)[0];
}

const isDict = (v: unknown): v is Dict => typeof v === "object" && v !== null && !Array.isArray(v);

export function scrubEvent<T>(event: T): T {
  const e = event as unknown as Dict;
  const request = e.request;
  if (isDict(request)) {
    delete request.cookies;
    delete request.data;
    delete request.query_string;
    if (typeof request.url === "string") request.url = stripQuery(request.url);
    if (isDict(request.headers)) {
      request.headers = Object.fromEntries(
        Object.entries(request.headers).filter(([k]) => !DROP_HEADERS.has(k.toLowerCase())),
      );
    }
  }
  if (isDict(e.user)) e.user = e.user.id ? { id: e.user.id } : {};
  if (typeof e.message === "string") e.message = redact(e.message);

  const exception = e.exception;
  if (isDict(exception) && Array.isArray(exception.values)) {
    for (const value of exception.values) {
      if (isDict(value) && typeof value.value === "string") value.value = redact(value.value);
    }
  }

  const crumbs = Array.isArray(e.breadcrumbs) ? e.breadcrumbs : isDict(e.breadcrumbs) ? e.breadcrumbs.values : null;
  if (Array.isArray(crumbs)) {
    for (const crumb of crumbs) {
      if (!isDict(crumb)) continue;
      if (typeof crumb.message === "string") crumb.message = redact(crumb.message);
      if (isDict(crumb.data)) {
        for (const key of ["url", "from", "to"]) {
          if (typeof crumb.data[key] === "string") crumb.data[key] = stripQuery(crumb.data[key] as string);
        }
      }
    }
  }
  return event;
}

/** Settings shared by every runtime, or null when error tracking is off (no DSN). */
export function sentryOptions(env: {
  dsn?: string;
  environment?: string;
  release?: string;
  tracesSampleRate?: string;
}) {
  if (!env.dsn) return null;
  const rate = Number(env.tracesSampleRate ?? "0");
  return {
    dsn: env.dsn,
    environment: env.environment || "development",
    release: env.release || undefined,
    tracesSampleRate: Number.isFinite(rate) && rate >= 0 && rate <= 1 ? rate : 0,
    sendDefaultPii: false,
    // Sentry 11 streams spans by default, and then ignores beforeSendTransaction, so traces would
    // go out unscrubbed. "static" sends them as transactions, through scrubEvent.
    traceLifecycle: "static" as const,
    beforeSend: scrubEvent,
    beforeSendTransaction: scrubEvent,
    beforeBreadcrumb<B>(crumb: B): B {
      return scrubEvent({ breadcrumbs: [crumb] }).breadcrumbs[0];
    },
  };
}
