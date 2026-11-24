/** Server-side error tracking (Node and Edge), off unless NEXT_PUBLIC_SENTRY_DSN is set. */
import { webSentryOptions } from "./lib/error-reporting";

export async function register() {
  const options = webSentryOptions();
  if (!options) return;
  const Sentry = await import("@sentry/nextjs");
  Sentry.init(options);
}

type CaptureArgs = Parameters<typeof import("@sentry/nextjs").captureRequestError>;

/** Errors thrown while rendering or in route handlers on the server. */
export async function onRequestError(...args: CaptureArgs) {
  if (!webSentryOptions()) return;
  const Sentry = await import("@sentry/nextjs");
  Sentry.captureRequestError(...args);
}
