import { sentryOptions } from "./sentry-scrub";

/** Error tracking settings from the build's public env; null means it's off. */
export function webSentryOptions() {
  return sentryOptions({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT,
    // On Vercel the commit SHA is exposed automatically; elsewhere set NEXT_PUBLIC_APP_RELEASE.
    release: process.env.NEXT_PUBLIC_APP_RELEASE || process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA,
    tracesSampleRate: process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE,
  });
}

export const errorTrackingEnabled = () => !!process.env.NEXT_PUBLIC_SENTRY_DSN;

/**
 * Report an error caught by an error boundary. The SDK is loaded on demand, so builds without a DSN
 * ship none of it.
 */
export function reportError(error: unknown): void {
  if (!errorTrackingEnabled()) return;
  void import("@sentry/nextjs").then((Sentry) => Sentry.captureException(error)).catch(() => undefined);
}
