/**
 * One realtime connection per browser tab, shared by everything that listens (the messages
 * page, the notification bell, the notifications page). The first subscriber opens it; it
 * closes a moment after the last one leaves, so moving between pages doesn't reconnect.
 *
 * Browser pieces (WebSocket, localStorage, window events) are passed in, so the connection
 * rules can be tested without a browser. See hooks/useSocket.ts for the React side.
 */
import { HEARTBEAT_INTERVAL_MS, closeAction, isStale, reconnectDelay } from "./realtime.ts";

export type SocketStatus = "idle" | "connecting" | "open" | "offline";

export interface Envelope {
  event: string;
  data?: any;
  [key: string]: unknown;
}

export interface HubListener {
  onEnvelope?: (envelope: Envelope) => void;
  onStatus?: (status: SocketStatus) => void;
  /** The connection came back after a drop: refetch anything that may have been missed. */
  onReconnected?: () => void;
}

/** The parts of a browser WebSocket the hub uses. */
export interface SocketLike {
  readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  onopen: ((event: unknown) => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onclose: ((event: { code: number }) => void) | null;
  onerror: ((event: unknown) => void) | null;
}

export const SOCKET_OPEN = 1;
const SOCKET_CLOSING = 2;
const SOCKET_CLOSED = 3;

/** How long the connection stays open after the last subscriber leaves. */
export const LINGER_MS = 1_000;

export interface HubDeps {
  url: string;
  createSocket(url: string): SocketLike;
  getToken(): string | null;
  /** New access token, null when signed out; rejects when offline. */
  refreshToken(): Promise<string | null>;
  isOnline(): boolean;
  /** Wire up the browser's online/offline/visible events; returns a function that unwires them. */
  watchBrowser?(handlers: { online(): void; offline(): void; visible(): void }): () => void;
}

export class SocketHub {
  private readonly listeners = new Set<HubListener>();
  private socket: SocketLike | null = null;
  private current: SocketStatus = "idle";
  private userKey: string | null = null;
  private running = false;
  private attempts = 0;
  private everConnected = false;
  private lastFrameAt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeat: ReturnType<typeof setInterval> | null = null;
  private lingerTimer: ReturnType<typeof setTimeout> | null = null;
  private unwatch: (() => void) | null = null;

  private readonly deps: HubDeps;

  constructor(deps: HubDeps) {
    this.deps = deps;
  }

  get status(): SocketStatus {
    return this.current;
  }

  get subscriberCount(): number {
    return this.listeners.size;
  }

  /**
   * Listen on the tab's connection, opening it if needed. `userKey` identifies the signed-in
   * account: a different account never reuses the previous one's connection.
   */
  subscribe(listener: HubListener, userKey: string): () => void {
    if (this.lingerTimer) {
      clearTimeout(this.lingerTimer);
      this.lingerTimer = null;
    }
    if (this.running && userKey !== this.userKey) this.stop();
    this.userKey = userKey;
    this.listeners.add(listener);
    safely(() => listener.onStatus?.(this.current));
    if (!this.running) this.start();

    let left = false;
    return () => {
      if (left) return;
      left = true;
      this.listeners.delete(listener);
      if (this.listeners.size === 0 && this.running && !this.lingerTimer) {
        this.lingerTimer = setTimeout(() => {
          this.lingerTimer = null;
          if (this.listeners.size === 0) this.stop();
        }, LINGER_MS);
      }
    };
  }

  send(event: string, data: Record<string, unknown>): boolean {
    const ws = this.socket;
    if (!ws || ws.readyState !== SOCKET_OPEN) return false;
    ws.send(JSON.stringify({ version: "1.0", event, timestamp: new Date().toISOString(), data }));
    return true;
  }

  /** Reconnect at once if the connection is down (browser back online, tab shown). */
  reconnectNow(): void {
    if (!this.running) return;
    const ws = this.socket;
    if (!ws || ws.readyState === SOCKET_CLOSED || ws.readyState === SOCKET_CLOSING) {
      this.attempts = 0;
      this.connect();
    }
  }

  // ------------------------------------------------------------------ lifecycle

  private start(): void {
    this.running = true;
    this.attempts = 0;
    this.everConnected = false;
    this.unwatch = this.deps.watchBrowser?.({
      online: () => this.reconnectNow(),
      offline: () => this.setStatus("offline"),
      visible: () => this.reconnectNow(),
    }) ?? null;
    this.connect();
  }

  private stop(): void {
    this.running = false;
    this.clearTimers();
    this.unwatch?.();
    this.unwatch = null;
    const ws = this.socket;
    this.socket = null;
    ws?.close(1000, "unmount");
    this.setStatus("idle");
  }

  private connect(): void {
    if (!this.running) return;
    if (!this.deps.isOnline()) {
      this.setStatus("offline");
      return; // the "online" event reconnects
    }
    const token = this.deps.getToken();
    if (!token) return;

    const previous = this.socket;
    this.socket = null; // its close handler must not schedule anything now
    previous?.close(1000, "replaced");
    this.clearTimers();

    this.setStatus("connecting");
    const ws = this.deps.createSocket(this.deps.url);
    this.socket = ws;
    this.lastFrameAt = Date.now();

    ws.onopen = () => {
      if (this.socket !== ws) return;
      ws.send(JSON.stringify({ version: "1.0", event: "auth", data: { token } }));
      this.heartbeat = setInterval(() => {
        if (ws.readyState !== SOCKET_OPEN) return;
        if (isStale(this.lastFrameAt, Date.now())) {
          ws.close(4000, "stale"); // dead connection: reconnect
          return;
        }
        ws.send(JSON.stringify({ version: "1.0", event: "ping", data: {} }));
      }, HEARTBEAT_INTERVAL_MS);
    };

    ws.onmessage = (event) => {
      if (this.socket !== ws) return;
      this.lastFrameAt = Date.now();
      let envelope: Envelope;
      try {
        envelope = JSON.parse(event.data);
      } catch {
        return; // ignore malformed frames
      }
      this.dispatch(envelope);
    };

    ws.onclose = (event) => {
      if (this.socket !== ws) return; // a replaced or stopped socket: nothing to do
      this.socket = null;
      this.clearTimers();
      if (!this.running) return;
      const action = closeAction(event.code, false);
      if (action === "stop") {
        this.setStatus("idle");
        return;
      }
      this.setStatus(this.deps.isOnline() ? "connecting" : "offline");
      if (action === "refresh") {
        this.deps.refreshToken().then(
          (newToken) => {
            if (newToken) this.scheduleReconnect(0);
            else this.setStatus("idle"); // signed out: the auth store takes over
          },
          () => this.scheduleReconnect(reconnectDelay(this.attempts++)), // offline: keep the session, retry
        );
        return;
      }
      this.scheduleReconnect(reconnectDelay(this.attempts++));
    };

    ws.onerror = () => {
      // onclose follows and decides what to do
    };
  }

  private dispatch(envelope: Envelope): void {
    if (envelope.event === "connection.ready") {
      this.attempts = 0;
      this.setStatus("open");
      if (this.everConnected) this.each((l) => l.onReconnected?.());
      this.everConnected = true;
    }
    this.each((l) => l.onEnvelope?.(envelope));
  }

  private scheduleReconnect(delay: number): void {
    if (!this.running) return;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  private clearTimers(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.heartbeat) clearInterval(this.heartbeat);
    this.reconnectTimer = this.heartbeat = null;
  }

  private setStatus(status: SocketStatus): void {
    if (status === this.current) return;
    this.current = status;
    this.each((l) => l.onStatus?.(status));
  }

  /** Call every listener; one that throws must not stop the others. */
  private each(fn: (listener: HubListener) => void): void {
    for (const listener of Array.from(this.listeners)) safely(() => fn(listener));
  }
}

function safely(fn: () => void): void {
  try {
    fn();
  } catch (err) {
    console.error("Realtime listener failed", err);
  }
}
