import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DELETION_GRACE_DAYS, deletedNoticeDate, deletionConsequences, deletionDateLabel, exportFileName,
} from "../lib/account-data-model.ts";

test("deletion dates read as a calendar date in India", () => {
  // 20:00 UTC is already the next day in India.
  assert.equal(deletionDateLabel("2026-12-23T20:00:00+00:00"), "24 December 2026");
  assert.equal(deletionDateLabel(""), "");
  assert.equal(deletionDateLabel("not a date"), "");
});

test("the login notice only shows for a real date", () => {
  assert.equal(deletedNoticeDate("2026-12-24T06:00:00Z"), "24 December 2026");
  assert.equal(deletedNoticeDate("<script>"), null);
  assert.equal(deletedNoticeDate(null), null);
});

test("export file is named by day", () => {
  assert.equal(exportFileName(new Date(2026, 10, 4)), "flatmate-data-20261104.json");
});

test("the confirmation says what is kept, removed and how to undo", () => {
  const text = deletionConsequences().join(" ");
  assert.equal(DELETION_GRACE_DAYS, 30);
  for (const phrase of ["signed out", "Deleted user", "Payment records are kept", "Sign in within 30 days", "listing was removed"]) {
    assert.ok(text.includes(phrase), phrase);
  }
});
