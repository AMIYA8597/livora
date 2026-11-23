/**
 * Pure rules for the chat socket (kept free of React and browser globals so they can be tested).
 */

/** Close codes sent by the API (see apps/api/app/modules/messaging/router.py). */
export const WS_CLOSE_TOKEN_EXPIRED = 4001;
export const WS_CLOSE_UNAUTHORIZED = 4003;
/** The server refused because the user has too many open sockets (policy violation). */
export const WS_CLOSE_POLICY = 1008;

export type CloseAction =
  /** Renew the access token, then reconnect at once. */
  | "refresh"
  /** Reconnect after a backoff delay. */
  | "backoff"
  /** Don't reconnect (we closed it on purpose, or the server refused us). */
  | "stop";

export function closeAction(code: number, closedByUs: boolean): CloseAction {
  if (closedByUs) return "stop";
  if (code === WS_CLOSE_TOKEN_EXPIRED || code === WS_CLOSE_UNAUTHORIZED) return "refresh";
  if (code === WS_CLOSE_POLICY) return "stop";
  return "backoff";
}

/** Exponential backoff with jitter: about 1s, 1.5s, 2.3s … capped at 30s. */
export function reconnectDelay(attempt: number, random: () => number = Math.random): number {
  const base = Math.min(1000 * 1.5 ** attempt, 30_000);
  return Math.round(base * (0.75 + random() * 0.5));
}

/** The socket URL: NEXT_PUBLIC_WS_URL, else derived from the API URL. Never carries a token. */
export function socketUrl(apiBaseUrl: string, explicit?: string): string {
  if (explicit) return explicit;
  return `${apiBaseUrl.replace(/^http/, "ws").replace(/\/$/, "")}/messaging/ws`;
}

/** No frame (not even a pong) for this long means the connection is dead (e.g. after sleep). */
export const HEARTBEAT_INTERVAL_MS = 25_000;
export const STALE_AFTER_MS = 2 * HEARTBEAT_INTERVAL_MS + 10_000;

export function isStale(lastFrameAt: number, now: number): boolean {
  return now - lastFrameAt > STALE_AFTER_MS;
}
