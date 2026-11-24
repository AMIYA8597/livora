/**
 * Browser error tracking. Off (and not downloaded) unless NEXT_PUBLIC_SENTRY_DSN was set at build
 * time. No session replay: it would record what people type and read.
 *
 * The SDK (about 170 KB, ~180 ms of main-thread work on a mid-range phone) stays out of page
 * start-up. With performance tracing off (the default) it is fetched only when the first error
 * happens, like Sentry's own lazy loader; that error and any after it are sent once it's ready
 * (lib/deferred-errors.ts). With tracing on it is fetched once the page has loaded and gone idle.
 */
import { webSentryOptions } from "./lib/error-reporting";
import { browserErrors, listenForEarlyErrors, whenIdleAfterLoad } from "./lib/deferred-errors";

type NavigationType = "push" | "replace" | "traverse";
let onTransition: ((href: string, navigationType: NavigationType) => void) | null = null;

const options = webSentryOptions();
if (options && typeof window !== "undefined") {
  const stopListening = listenForEarlyErrors(window, browserErrors.capture);
  let started = false;
  const start = () => {
    if (started) return;
    started = true;
    void import("./lib/sentry-browser")
      .then((Sentry) => {
        Sentry.init(options);
        stopListening(); // Sentry's own handlers take over from here
        onTransition = Sentry.captureRouterTransitionStart;
        browserErrors.ready(Sentry);
      })
      .catch(() => stopListening());
  };
  browserErrors.whenWaiting(start);
  if (options.tracesSampleRate > 0) whenIdleAfterLoad(window, start);
}

export function onRouterTransitionStart(href: string, navigationType: NavigationType) {
  onTransition?.(href, navigationType);
}
