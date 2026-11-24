import test from "node:test";
import assert from "node:assert";
import { createErrorQueue, listenForEarlyErrors, whenIdleAfterLoad } from "../lib/deferred-errors.ts";

function fakeWindow(readyState: string, idle = true) {
  const listeners = new Map<string, Set<(e: any) => void>>();
  const calls: string[] = [];
  const win = {
    document: { readyState },
    addEventListener(type: string, fn: (e: any) => void) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)!.add(fn);
    },
    removeEventListener(type: string, fn: (e: any) => void) {
      listeners.get(type)?.delete(fn);
    },
    requestIdleCallback: idle
      ? (cb: () => void, opts?: { timeout: number }) => {
          calls.push(`idle:${opts?.timeout}`);
          cb();
        }
      : undefined,
    setTimeout(cb: () => void, ms: number) {
      calls.push(`timeout:${ms}`);
      cb();
    },
    fire(type: string, event: unknown) {
      for (const fn of Array.from(listeners.get(type) ?? [])) fn(event);
    },
    count(type: string) {
      return listeners.get(type)?.size ?? 0;
    },
    calls,
  };
  return win;
}

test("errors wait for the SDK, then go straight through", () => {
  const q = createErrorQueue(2);
  q.capture("a");
  q.capture("b");
  q.capture("c"); // over the limit: dropped
  const sent: unknown[] = [];
  q.ready({ captureException: (e) => sent.push(e) });
  assert.deepStrictEqual(sent, ["a", "b"]);
  assert.strictEqual(q.size, 0);
  q.capture("d");
  assert.deepStrictEqual(sent, ["a", "b", "d"]);
});

test("the first waiting error asks for the SDK to be loaded", () => {
  const q = createErrorQueue();
  let asked = 0;
  q.whenWaiting(() => asked++);
  assert.strictEqual(asked, 0); // nothing has gone wrong: nothing is loaded
  q.capture("first");
  assert.strictEqual(asked, 1);
  q.ready({ captureException: () => undefined });
  q.capture("after");
  assert.strictEqual(asked, 1); // ready: errors go straight to the SDK

  const early = createErrorQueue();
  early.capture("before anyone listened");
  let late = 0;
  early.whenWaiting(() => late++);
  assert.strictEqual(late, 1);
});

test("early uncaught errors and rejections are collected until stopped", () => {
  const win = fakeWindow("loading");
  const got: unknown[] = [];
  const stop = listenForEarlyErrors(win, (e) => got.push(e));
  const boom = new Error("boom");
  win.fire("error", { error: boom });
  win.fire("error", { message: "Script error." });
  win.fire("unhandledrejection", { reason: "nope" });
  assert.strictEqual(got[0], boom);
  assert.ok(got[1] instanceof Error && (got[1] as Error).message === "Script error.");
  assert.strictEqual(got[2], "nope");
  stop();
  assert.strictEqual(win.count("error") + win.count("unhandledrejection"), 0);
});

test("the SDK starts only after load, when the browser is idle", () => {
  const loading = fakeWindow("loading");
  let started = 0;
  whenIdleAfterLoad(loading, () => started++, 4000);
  assert.strictEqual(started, 0);
  loading.fire("load", {});
  assert.strictEqual(started, 1);
  assert.deepStrictEqual(loading.calls, ["idle:4000"]);

  const loaded = fakeWindow("complete", false); // no requestIdleCallback (Safari)
  whenIdleAfterLoad(loaded, () => started++);
  assert.strictEqual(started, 2);
  assert.deepStrictEqual(loaded.calls, ["timeout:1500"]);
});
