import { test } from "node:test";
import assert from "node:assert/strict";
import { overrideTargets, reasonProblem, statusLabel, statusTone } from "../lib/admin-applications-model.ts";

test("override choices skip the current status and its synonyms", () => {
  assert.deepEqual(overrideTargets("submitted"), ["under_review", "accepted", "rejected", "withdrawn"]);
  assert.deepEqual(overrideTargets("reviewing"), ["accepted", "rejected", "withdrawn"]);
  assert.deepEqual(overrideTargets("approved"), ["under_review", "rejected", "withdrawn"]);
  assert.ok(!overrideTargets("rejected").includes("rejected"));
  assert.ok(!overrideTargets("withdrawn").some((s) => (s as string) === "submitted"));
});

test("a reason is required and bounded", () => {
  assert.ok(reasonProblem(""));
  assert.ok(reasonProblem("  ok  "));
  assert.equal(reasonProblem("Owner confirmed by phone"), null);
  assert.ok(reasonProblem("x".repeat(501)));
});

test("labels and tones", () => {
  assert.equal(statusLabel("under_review"), "Under review");
  assert.equal(statusLabel("approved"), "Accepted");
  assert.equal(statusLabel("something_new"), "something new");
  assert.equal(statusTone("approved"), "success");
  assert.equal(statusTone("rejected"), "danger");
});
