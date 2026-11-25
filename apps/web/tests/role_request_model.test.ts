import test from "node:test";
import assert from "node:assert";
import { brokerAccess, decisionProblem, roleLabel, type RoleRequest } from "../lib/role-request-model.ts";

const req = (status: RoleRequest["status"], created_at: string, extra: Partial<RoleRequest> = {}): RoleRequest => ({
  id: created_at,
  role: "broker",
  status,
  note: null,
  decision_note: null,
  created_at,
  decided_at: null,
  ...extra,
});

test("a held broker role wins over any request", () => {
  assert.deepStrictEqual(brokerAccess(["owner", "broker"], [req("declined", "2026-11-01T00:00:00Z")]), { state: "broker" });
});

test("the newest request decides what the card shows", () => {
  const old = req("declined", "2026-11-01T00:00:00Z", { decision_note: "No RERA number" });
  const now = req("pending", "2026-11-20T00:00:00Z");
  assert.strictEqual(brokerAccess(["seeker"], [old, now]).state, "pending");
  assert.strictEqual(brokerAccess(["seeker"], [now, old]).state, "pending");
  const declined = brokerAccess(["seeker"], [old]);
  assert.strictEqual(declined.state, "declined");
  assert.strictEqual(declined.state === "declined" && declined.request.decision_note, "No RERA number");
});

test("no requests (or only an approved one whose role was later removed) means ask", () => {
  assert.deepStrictEqual(brokerAccess(["seeker"], []), { state: "none" });
  assert.deepStrictEqual(brokerAccess(["seeker"], [req("approved", "2026-11-01T00:00:00Z")]), { state: "none" });
});

test("a decline needs a reason; an approval doesn't", () => {
  assert.ok(decisionProblem(false, "   "));
  assert.strictEqual(decisionProblem(false, "RERA number didn't match"), null);
  assert.strictEqual(decisionProblem(true, ""), null);
  assert.ok(decisionProblem(true, "x".repeat(501)));
});

test("role labels read naturally", () => {
  assert.strictEqual(roleLabel("pg_operator"), "PG operator");
  assert.strictEqual(roleLabel("super_admin"), "Super admin");
  assert.strictEqual(roleLabel("some_new_role"), "some new role");
});
