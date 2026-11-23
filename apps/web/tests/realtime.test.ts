import { test } from "node:test";
import assert from "node:assert/strict";
import { STALE_AFTER_MS, closeAction, isStale, reconnectDelay, socketUrl } from "../lib/realtime.ts";

test("realtime: close codes decide whether to renew the token, back off or stop", () => {
  assert.equal(closeAction(4001, false), "refresh"); // token expired
  assert.equal(closeAction(4003, false), "refresh"); // try a fresh token once; null means signed out
  assert.equal(closeAction(1006, false), "backoff"); // network drop
  assert.equal(closeAction(1008, false), "stop"); // too many tabs open
  assert.equal(closeAction(1006, true), "stop"); // we closed it
});

test("realtime: backoff grows, is jittered and is capped", () => {
  assert.equal(reconnectDelay(0, () => 0.5), 1000);
  assert.equal(reconnectDelay(2, () => 0.5), 2250);
  assert.equal(reconnectDelay(50, () => 0.5), 30_000);
  assert.ok(reconnectDelay(0, () => 0) >= 750 && reconnectDelay(0, () => 1) <= 1250);
});

test("realtime: the socket URL never carries a token", () => {
  assert.equal(socketUrl("https://api.example.in/api/v1"), "wss://api.example.in/api/v1/messaging/ws");
  assert.equal(socketUrl("http://127.0.0.1:8000/api/v1/"), "ws://127.0.0.1:8000/api/v1/messaging/ws");
  assert.equal(socketUrl("x", "wss://chat.example.in/ws"), "wss://chat.example.in/ws");
});

test("realtime: a silent connection is treated as dead", () => {
  assert.equal(isStale(0, STALE_AFTER_MS), false);
  assert.equal(isStale(0, STALE_AFTER_MS + 1), true);
});
