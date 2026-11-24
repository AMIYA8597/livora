/**
 * Error tracking without slowing page start-up (see instrumentation-client.ts): the Sentry SDK is
 * fetched when the first error happens or, with performance tracing on, once the page has loaded
 * and the main thread is idle. Errors raised before it's ready are held here, up to a limit, and
 * handed over when it is. Pure (no imports), so it is unit-tested with fake windows.
 */

export interface ErrorSink {
  captureException(error: unknown): unknown;
}

export const EARLY_ERROR_LIMIT = 20;

/** Holds errors until a sink is ready, then passes everything straight through. */
export function createErrorQueue(limit = EARLY_ERROR_LIMIT) {
  let sink: ErrorSink | null = null;
  let onWaiting: (() => void) | null = null;
  const pending: unknown[] = [];
  return {
    capture(error: unknown): void {
      if (sink) {
        sink.captureException(error);
        return;
      }
      if (pending.length < limit) pending.push(error);
      onWaiting?.();
    },
    /** Called whenever an error is waiting for the SDK (straight away if one already is). */
    whenWaiting(cb: () => void): void {
      onWaiting = cb;
      if (pending.length > 0) cb();
    },
    ready(next: ErrorSink): void {
      sink = next;
      for (const error of pending.splice(0)) next.captureException(error);
    },
    get size(): number {
      return pending.length;
    },
  };
}

type Listener = (event: any) => void;
interface EventTargetLike {
  addEventListener(type: string, listener: Listener, options?: unknown): void;
  removeEventListener(type: string, listener: Listener): void;
}

/** Uncaught errors and unhandled rejections, until the returned function is called. */
export function listenForEarlyErrors(win: EventTargetLike, onError: (error: unknown) => void): () => void {
  const onErrorEvent: Listener = (e) => onError(e?.error ?? new Error(String(e?.message ?? "Script error")));
  const onRejection: Listener = (e) => onError(e?.reason);
  win.addEventListener("error", onErrorEvent);
  win.addEventListener("unhandledrejection", onRejection);
  return () => {
    win.removeEventListener("error", onErrorEvent);
    win.removeEventListener("unhandledrejection", onRejection);
  };
}

export interface IdleWindow extends EventTargetLike {
  document: { readyState: string };
  requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => unknown;
  setTimeout(cb: () => void, ms: number): unknown;
}

/** Runs `cb` once the page has loaded and the browser is idle (or after `maxWaitMs` at most). */
export function whenIdleAfterLoad(win: IdleWindow, cb: () => void, maxWaitMs = 5000): void {
  const schedule = () => {
    if (typeof win.requestIdleCallback === "function") win.requestIdleCallback(cb, { timeout: maxWaitMs });
    else win.setTimeout(cb, 1500);
  };
  if (win.document.readyState === "complete") schedule();
  else win.addEventListener("load", schedule, { once: true });
}

/** The app-wide queue: error boundaries and the early listeners both feed it. */
export const browserErrors = createErrorQueue();
