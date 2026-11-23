import test from "node:test";
import assert from "node:assert";
import * as store from "../lib/auth-store.ts";

class MemoryStorage {
  store: Record<string, string> = {};
  getItem(k: string) { return k in this.store ? this.store[k] : null; }
  setItem(k: string, v: string) { this.store[k] = String(v); }
  removeItem(k: string) { delete this.store[k]; }
  clear() { this.store = {}; }
}
const storage = new MemoryStorage();
const handlers: Record<string, ((e: any) => void)[]> = {};
(globalThis as any).localStorage = storage;
(globalThis as any).window = {
  addEventListener: (t: string, h: (e: any) => void) => { (handlers[t] ||= []).push(h); },
  dispatchEvent: (e: { type: string }) => { (handlers[e.type] || []).forEach((h) => h(e)); return true; },
};
(globalThis as any).CustomEvent = class { type: string; constructor(t: string) { this.type = t; } };

// auth-store touches window/localStorage only when used, so a static import is safe here.

const user = {
  id: "u1", email: "a@example.in", full_name: "A", role: "seeker", roles: ["seeker", "owner"],
  is_active: true, is_verified: true, created_at: "2026-01-01T00:00:00Z",
} as const;

function mockFetch(handler: (url: string) => Response | Promise<Response>) {
  globalThis.fetch = (async (url: string | URL | Request) => handler(String(url))) as typeof fetch;
}
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const flush = () => new Promise((r) => setTimeout(r, 0));

test.beforeEach(() => {
  storage.clear();
  store.__resetAuthStoreForTests();
});

test("no token: anonymous without calling the API", async () => {
  let called = false;
  mockFetch(() => { called = true; return json(200, user); });
  await store.refreshAuth();
  assert.strictEqual(store.getSnapshot().status, "anonymous");
  assert.strictEqual(called, false);
});

test("roles come from the server, not from localStorage", async () => {
  storage.setItem("flatmate_access_token", "t");
  storage.setItem("flatmate_user_roles", JSON.stringify(["super_admin"]));
  mockFetch(() => json(200, { ...user, roles: ["seeker"] }));
  store.subscribe(() => {}); // starts the store; drops the legacy roles key
  await flush(); await flush();
  const s = store.getSnapshot();
  assert.strictEqual(s.status, "authenticated");
  assert.deepStrictEqual(s.roles, ["seeker"]);
  assert.strictEqual(store.hasRoleIn(s, "admin"), false);
  assert.strictEqual(storage.getItem("flatmate_user_roles"), null);
});

test("network failure keeps the tokens (no surprise sign-out)", async () => {
  storage.setItem("flatmate_access_token", "t");
  mockFetch(() => { throw new TypeError("Failed to fetch"); });
  await store.refreshAuth();
  assert.strictEqual(store.getSnapshot().status, "error");
  assert.strictEqual(storage.getItem("flatmate_access_token"), "t");
});

test("after a network failure the store recovers by itself (backoff timer)", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  storage.setItem("flatmate_access_token", "t");
  let up = false;
  mockFetch(() => {
    if (!up) throw new TypeError("Failed to fetch");
    return json(200, user);
  });
  await store.refreshAuth();
  assert.strictEqual(store.getSnapshot().status, "error");

  up = true;
  t.mock.timers.tick(2_000);
  t.mock.timers.reset(); // let the fetch promise chain settle on real timers
  await flush(); await flush();
  assert.strictEqual(store.getSnapshot().status, "authenticated");
});

test("coming back online retries at once; a 401 then still signs out", async () => {
  storage.setItem("flatmate_access_token", "t");
  let answer: "down" | "401" = "down";
  mockFetch(() => {
    if (answer === "down") throw new TypeError("Failed to fetch");
    return json(401, { detail: "expired" });
  });
  store.subscribe(() => {}); // registers the online/focus listeners
  await flush(); await flush();
  assert.strictEqual(store.getSnapshot().status, "error");

  answer = "401";
  (globalThis as any).window.dispatchEvent({ type: "online" });
  await flush(); await flush(); await flush();
  assert.strictEqual(store.getSnapshot().status, "anonymous");
});

test("403 clears the session", async () => {
  storage.setItem("flatmate_access_token", "t");
  mockFetch(() => json(403, { detail: "User account has been deactivated" }));
  await store.refreshAuth();
  assert.strictEqual(store.getSnapshot().status, "anonymous");
  assert.strictEqual(storage.getItem("flatmate_access_token"), null);
});

test("signIn publishes the user to every subscriber", () => {
  let notified = 0;
  store.subscribe(() => { notified++; });
  store.subscribe(() => { notified++; });
  const before = notified;
  store.signIn({ access_token: "a", refresh_token: "r", token_type: "bearer", expires_in: 900 }, user as any, ["owner"]);
  assert.strictEqual(notified - before, 2);
  assert.deepStrictEqual(store.getSnapshot().roles, ["owner", "seeker"]);
  assert.strictEqual(storage.getItem("flatmate_access_token"), "a");
});

test("a stale /auth/me response cannot overwrite a newer sign-out", async () => {
  storage.setItem("flatmate_access_token", "t");
  let release!: () => void;
  mockFetch((url) => url.endsWith("/auth/me")
    ? new Promise<Response>((r) => { release = () => r(json(200, user)); })
    : json(200, { success: true }));
  const pending = store.refreshAuth();
  await store.signOut();
  release();
  await pending;
  assert.strictEqual(store.getSnapshot().status, "anonymous");
});

test("admin role grants every role check", () => {
  store.signIn({ access_token: "a", refresh_token: "r", token_type: "bearer", expires_in: 900 }, { ...user, role: "admin", roles: [] } as any);
  assert.strictEqual(store.hasRoleIn(store.getSnapshot(), "owner"), true);
});
