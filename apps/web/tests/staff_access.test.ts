import test from "node:test";
import assert from "node:assert";
import {
  canGrantRole,
  canManageAccount,
  consoleTabs,
  grantableRoles,
  isAdminRoles,
  isStaffRoles,
  removableRoles,
} from "../lib/staff-access.ts";

test("admins and super admins see every console tab", () => {
  for (const roles of [["admin"], ["super_admin"], ["seeker", "admin"]]) {
    assert.deepStrictEqual(consoleTabs(roles), [
      "stats", "traffic", "moderation", "properties", "applications", "users", "roles", "payments",
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

test("only a super admin hands out or takes away admin roles", () => {
  assert.ok(canGrantRole(["super_admin"], "super_admin"));
  assert.ok(canGrantRole(["super_admin"], "admin"));
  assert.ok(canGrantRole(["admin"], "moderator"));
  assert.ok(canGrantRole(["admin"], "broker"));
  assert.ok(!canGrantRole(["admin"], "admin"));
  assert.ok(!canGrantRole(["admin"], "super_admin"));
  assert.ok(!canGrantRole(["moderator"], "broker"));
  assert.ok(!canGrantRole(["super_admin"], "root"));
});

test("admins can't change other admins' accounts; super admins can", () => {
  assert.ok(canManageAccount(["admin"], ["seeker", "moderator"]));
  assert.ok(!canManageAccount(["admin"], ["owner", "admin"]));
  assert.ok(!canManageAccount(["admin"], ["super_admin"]));
  assert.ok(canManageAccount(["super_admin"], ["admin"]));
  assert.ok(!canManageAccount(["moderator"], ["seeker"]));
});

test("the role picker offers only roles the account lacks and the actor may grant", () => {
  assert.deepStrictEqual(grantableRoles(["admin"], ["seeker"]), ["tenant", "owner", "pg_operator", "broker", "moderator"]);
  assert.deepStrictEqual(
    grantableRoles(["super_admin"], ["seeker", "broker"]),
    ["tenant", "owner", "pg_operator", "moderator", "admin", "super_admin"],
  );
});

test("the main role and your own staff role are never offered for removal", () => {
  assert.deepStrictEqual(
    removableRoles(["admin"], { roles: ["seeker", "broker", "moderator"], role: "seeker", isSelf: false }),
    ["broker", "moderator"],
  );
  assert.deepStrictEqual(
    removableRoles(["super_admin"], { roles: ["seeker", "owner", "super_admin"], role: "seeker", isSelf: true }),
    ["owner"],
  );
  assert.deepStrictEqual(removableRoles(["admin"], { roles: ["owner", "admin"], role: "owner", isSelf: false }), []);
});
