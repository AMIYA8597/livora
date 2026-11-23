import test from "node:test";
import assert from "node:assert";
import { loginHref, safeNextPath } from "../lib/navigation.ts";

test("allows same-site paths", () => {
  assert.strictEqual(safeNextPath("/profile"), "/profile");
  assert.strictEqual(safeNextPath("/properties/abc?tab=rooms"), "/properties/abc?tab=rooms");
  assert.strictEqual(safeNextPath(encodeURIComponent("/messages")), "/messages");
});

test("rejects open redirects and junk", () => {
  for (const bad of [
    "https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)",
    "evil.example", "%2F%2Fevil.example", "/ok\nSet-Cookie:x", "%E0%A4%A",
  ]) {
    assert.strictEqual(safeNextPath(bad), "/dashboard", bad);
  }
});

test("missing or auth-page targets fall back", () => {
  assert.strictEqual(safeNextPath(null), "/dashboard");
  assert.strictEqual(safeNextPath("/login"), "/dashboard");
  assert.strictEqual(safeNextPath("/register?x=1"), "/dashboard");
  assert.strictEqual(safeNextPath("/loginhelp"), "/loginhelp");
});

test("loginHref round-trips", () => {
  const href = loginHref("/properties/1?a=b");
  const next = new URL(href, "https://flatmate.test").searchParams.get("next");
  assert.strictEqual(safeNextPath(next), "/properties/1?a=b");
});
