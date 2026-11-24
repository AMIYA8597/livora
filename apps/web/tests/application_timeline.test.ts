import { test } from "node:test";
import assert from "node:assert/strict";
import { actorLabel, timelineText } from "../lib/application-timeline.ts";

test("application timeline: entries read from the viewer's side", () => {
  const at = "2026-11-24T10:00:00Z";
  assert.equal(timelineText({ from_status: null, to_status: "submitted", actor: "applicant", created_at: at }, "applicant"),
    "Submitted by you");
  assert.equal(timelineText({ from_status: null, to_status: "submitted", actor: "applicant", created_at: at }, "owner"),
    "Submitted by the applicant");
  assert.equal(timelineText({ from_status: "submitted", to_status: "under_review", actor: "owner", created_at: at }, "applicant"),
    "Under review by the owner");
  assert.equal(timelineText({ from_status: "under_review", to_status: "rejected", actor: "support", created_at: at }, "owner"),
    "Rejected by Flatmate support");
});

test("application timeline: staff are never named and removed accounts read neutrally", () => {
  assert.equal(actorLabel("support", "applicant"), "Flatmate support");
  assert.equal(actorLabel("unknown", "owner"), "a former account");
});
