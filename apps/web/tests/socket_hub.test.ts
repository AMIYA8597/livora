import { test, mock } from "node:test";
import assert from "node:assert/strict";
import { LINGER_MS, SOCKET_OPEN, SocketHub, type HubListener, type SocketLike, type SocketStatus } from "../lib/socket-hub.ts";

class FakeSocket implements SocketLike {
  readyState = 0;
  sent: any[] = [];
  closedWith: number | null = null;
  onopen: SocketLike["onopen"] = null;
  onmessage: SocketLike["onmessage"] = null;
  onclose: SocketLike["onclose"] = null;
  onerror: SocketLike["onerror"] = null;
  send(data: string) {
    this.sent.push(JSON.parse(data));
  }
  close(code = 1000) {
    if (this.readyState === 3) return;
    this.closedWith = code;
    this.readyState = 3;
    this.onclose?.({ code });
  }
  // server side
  open() {
    this.readyState = SOCKET_OPEN;
    this.onopen?.({});
  }
  push(event: string, data: unknown = {}) {
    this.onmessage?.({ data: JSON.stringify({ event, data }) });
  }
  drop(code: number) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

function setup(refresh: () => Promise<string | null> = async () => "renewed") {
  const sockets: FakeSocket[] = [];
  let token: string | null = "token-1";
  const hub = new SocketHub({
    url: "ws://test/messaging/ws",
    createSocket: () => {
      const s = new FakeSocket();
      sockets.push(s);
      return s;
    },
    getToken: () => token,
    refreshToken: async () => {
      const t = await refresh();
      if (t) token = t;
      return t;
    },
    isOnline: () => true,
  });
  return { hub, sockets };
}

function recorder() {
  const events: string[] = [];
  const statuses: SocketStatus[] = [];
  let reconnected = 0;
  const listener: HubListener = {
    onEnvelope: (e) => events.push(e.event),
    onStatus: (s) => statuses.push(s),
    onReconnected: () => reconnected++,
  };
  return { listener, events, statuses, reconnected: () => reconnected };
}

const flush = () => new Promise<void>((resolve) => setImmediate(resolve));

test("socket hub: the bell and the page share one connection", () => {
  const { hub, sockets } = setup();
  const bell = recorder();
  const page = recorder();
  const offBell = hub.subscribe(bell.listener, "user-a");
  const offPage = hub.subscribe(page.listener, "user-a");
  assert.equal(sockets.length, 1);

  sockets[0].open();
  assert.deepEqual(sockets[0].sent[0], { version: "1.0", event: "auth", data: { token: "token-1" } });
  sockets[0].push("connection.ready");
  sockets[0].push("notification.created", { id: "n1" });
  assert.equal(hub.status, "open");
  for (const r of [bell, page]) {
    assert.deepEqual(r.events, ["connection.ready", "notification.created"]);
    assert.equal(r.statuses.at(-1), "open");
  }
  assert.equal(hub.send("typing.started", { conversation_id: "c" }), true);
  offBell();
  offPage();
});

test("socket hub: closes a moment after the last subscriber leaves, not on page changes", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "setInterval"] });
  const { hub, sockets } = setup();
  const off1 = hub.subscribe(recorder().listener, "user-a");
  sockets[0].open();
  sockets[0].push("connection.ready");

  off1(); // leaving one page ...
  t.mock.timers.tick(LINGER_MS / 2);
  const off2 = hub.subscribe(recorder().listener, "user-a"); // ... and arriving on the next
  t.mock.timers.tick(LINGER_MS * 2);
  assert.equal(sockets.length, 1);
  assert.equal(sockets[0].closedWith, null);

  off2();
  off2(); // calling it twice is harmless
  t.mock.timers.tick(LINGER_MS);
  assert.equal(sockets[0].closedWith, 1000);
  assert.equal(hub.status, "idle");
  assert.equal(hub.send("ping", {}), false);
});

test("socket hub: a different account never reuses the previous connection", () => {
  const { hub, sockets } = setup();
  hub.subscribe(recorder().listener, "user-a");
  sockets[0].open();
  hub.subscribe(recorder().listener, "user-b");
  assert.equal(sockets.length, 2);
  assert.equal(sockets[0].closedWith, 1000);
});

test("socket hub: a disabled account (4003) is not reconnected once the refresh is refused", async () => {
  const { hub, sockets } = setup(async () => null);
  const r = recorder();
  hub.subscribe(r.listener, "user-a");
  sockets[0].open();
  sockets[0].push("connection.ready");
  sockets[0].drop(4003);
  await flush();
  assert.equal(sockets.length, 1);
  assert.equal(hub.status, "idle");
});

test("socket hub: an expired token is renewed and everyone hears about the reconnection", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "setInterval"] });
  const { hub, sockets } = setup(async () => "token-2");
  const a = recorder();
  const b = recorder();
  hub.subscribe(a.listener, "user-a");
  hub.subscribe(b.listener, "user-a");
  sockets[0].open();
  sockets[0].push("connection.ready");

  sockets[0].drop(4001);
  await flush();
  t.mock.timers.tick(0);
  assert.equal(sockets.length, 2);
  sockets[1].open();
  assert.equal(sockets[1].sent[0].data.token, "token-2");
  sockets[1].push("connection.ready");
  assert.equal(a.reconnected(), 1);
  assert.equal(b.reconnected(), 1);
});

test("socket hub: one listener throwing doesn't stop the others", () => {
  const { hub, sockets } = setup();
  const errors = mock.method(console, "error", () => {});
  const good = recorder();
  hub.subscribe({ onEnvelope: () => { throw new Error("boom"); } }, "user-a");
  hub.subscribe(good.listener, "user-a");
  sockets[0].open();
  sockets[0].push("message.created", { id: "m" });
  assert.deepEqual(good.events, ["message.created"]);
  assert.equal(errors.mock.callCount(), 1);
  errors.mock.restore();
});
