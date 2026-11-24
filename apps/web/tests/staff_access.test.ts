import test from "node:test";
import assert from "node:assert";
import { consoleTabs, isAdminRoles, isStaffRoles } from "../lib/staff-access.ts";

test("admins and super admins see every console tab", () => {
  for (const roles of [["admin"], ["super_admin"], ["seeker", "admin"]]) {
    assert.deepStrictEqual(consoleTabs(roles), [
      "stats", "moderation", "properties", "applications", "users", "payments",
    ]);
    assert.ok(isAdminRoles(roles));
    assert.ok(isStaffRoles(roles));
  }
});

test("moderators see only the tabs their API access allows", () => {
  assert.deepStrictEqual(consoleTabs(["moderator"]), ["moderation", "applications"]);
  assert.deepStrictEqual(consoleTabs(["seeker", "moderator"]), ["moderation", "applications"]);
  assert.ok(isStaffRoles(["moderator"]));
  assert.ok(!isAdminRoles(["moderator"]));
});

test("everyone else has no console", () => {
  for (const roles of [[], ["seeker"], ["owner", "tenant"], ["pg_operator", "broker"]]) {
    assert.deepStrictEqual(consoleTabs(roles), []);
    assert.ok(!isStaffRoles(roles));
  }
});
