/**
 * Browser error tracking. Off (and not downloaded) unless NEXT_PUBLIC_SENTRY_DSN was set at build
 * time. No session replay: it would record what people type and read.
 */
import { webSentryOptions } from "./lib/error-reporting";

type NavigationType = "push" | "replace" | "traverse";
let onTransition: ((href: string, navigationType: NavigationType) => void) | null = null;

const options = webSentryOptions();
if (options) {
  void import("@sentry/nextjs").then((Sentry) => {
    Sentry.init(options);
    onTransition = Sentry.captureRouterTransitionStart;
  });
}

export function onRouterTransitionStart(href: string, navigationType: NavigationType) {
  onTransition?.(href, navigationType);
}
