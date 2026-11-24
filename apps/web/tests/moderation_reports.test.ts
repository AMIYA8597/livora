import test from "node:test";
import assert from "node:assert";
import { REPORT_STATUSES, reportNeedsAction } from "../lib/moderation-reports.ts";

test("open and under-investigation reports wait for a moderator", () => {
  assert.ok(reportNeedsAction("open"));
  assert.ok(reportNeedsAction("under_investigation"));
});

test("closed or unknown statuses do not", () => {
  for (const s of ["resolved", "dismissed", "pending", ""]) assert.ok(!reportNeedsAction(s), s);
});

test("the filter list matches what the API stores", () => {
  assert.deepStrictEqual([...REPORT_STATUSES], ["open", "under_investigation", "resolved", "dismissed"]);
});
