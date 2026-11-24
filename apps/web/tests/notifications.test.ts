import { test } from "node:test";
import assert from "node:assert/strict";
import {
  appendPage,
  dayGroup,
  groupByDay,
  mergeNotification,
  safeHref,
  timeAgo,
  urlBase64ToUint8Array,
} from "../lib/notifications-model.ts";

const n = (id: string, created_at: string, is_read = false) => ({ id, created_at, is_read });

test("notification links never leave the site", () => {
  assert.equal(safeHref("/matches"), "/matches");
  assert.equal(safeHref("/messages?conversationId=abc"), "/messages?conversationId=abc");
  for (const bad of ["https://evil.example", "//evil.example", "javascript:alert(1)", "/\\evil", "", null, undefined]) {
    assert.equal(safeHref(bad), "/notifications");
  }
});

test("live notifications merge without duplicates, newest first", () => {
  const list = [n("b", "2026-11-24T10:00:00Z"), n("a", "2026-11-24T09:00:00Z")];
  assert.deepEqual(mergeNotification(list, n("c", "2026-11-24T11:00:00Z")).map((x) => x.id), ["c", "b", "a"]);
  assert.deepEqual(mergeNotification(list, n("b", "2026-11-24T10:00:00Z", true)).map((x) => [x.id, x.is_read]), [
    ["b", true],
    ["a", false],
  ]);
  assert.deepEqual(appendPage(list, [n("a", "2026-11-24T09:00:00Z"), n("z", "2026-11-23T09:00:00Z")]).map((x) => x.id), [
    "b",
    "a",
    "z",
  ]);
});

test("grouped by day in local time", () => {
  const now = new Date(2026, 10, 24, 15, 0);
  assert.equal(dayGroup(new Date(2026, 10, 24, 0, 5).toISOString(), now), "Today");
  assert.equal(dayGroup(new Date(2026, 10, 23, 23, 55).toISOString(), now), "Yesterday");
  assert.equal(dayGroup(new Date(2026, 10, 19, 12, 0).toISOString(), now), "This week");
  assert.equal(dayGroup(new Date(2026, 9, 1).toISOString(), now), "Earlier");
  const groups = groupByDay(
    [n("1", new Date(2026, 10, 24, 9).toISOString()), n("2", new Date(2026, 10, 24, 8).toISOString()), n("3", new Date(2026, 10, 22).toISOString())],
    now,
  );
  assert.deepEqual(groups.map((g) => [g.label, g.items.length]), [["Today", 2], ["This week", 1]]);
});

test("relative times stay short", () => {
  const now = new Date("2026-11-24T12:00:00Z");
  assert.equal(timeAgo("2026-11-24T11:59:30Z", now), "just now");
  assert.equal(timeAgo("2026-11-24T11:55:00Z", now), "5m");
  assert.equal(timeAgo("2026-11-24T09:00:00Z", now), "3h");
  assert.equal(timeAgo("2026-11-22T12:00:00Z", now), "2d");
});

test("VAPID keys decode to the 65-byte public point", () => {
  const key = "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U";
  const bytes = urlBase64ToUint8Array(key);
  assert.equal(bytes.length, 65);
  assert.equal(bytes[0], 4);
});
