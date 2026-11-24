import test from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_RADIUS_KM, formatDistance, locationErrorMessage, nearParams, RADIUS_CHOICES, roundPoint } from "../lib/near-me.ts";

test("near me: the position is rounded to about 1 km before it is sent", () => {
  assert.deepEqual(roundPoint(12.934533, 77.626579), { lat: 12.93, lng: 77.63 });
  assert.deepEqual(roundPoint(-0.004, 0.005), { lat: -0, lng: 0.01 });
});

test("near me: query parameters only when it is on", () => {
  assert.deepEqual(nearParams(null, 10), {});
  assert.deepEqual(nearParams({ lat: 12.93, lng: 77.63 }, 5), { near_lat: 12.93, near_lng: 77.63, radius_km: 5 });
  assert.ok((RADIUS_CHOICES as readonly number[]).includes(DEFAULT_RADIUS_KM));
  assert.ok(RADIUS_CHOICES.every((r) => r >= 1 && r <= 100)); // the API's limits
});

test("near me: distances read naturally", () => {
  assert.equal(formatDistance(0.4), "Under 1 km away");
  assert.equal(formatDistance(2.44), "2.4 km away");
  assert.equal(formatDistance(18.6), "19 km away");
  assert.equal(formatDistance(null), null);
  assert.equal(formatDistance(undefined), null);
});

test("near me: every way of failing says what to do next", () => {
  assert.match(locationErrorMessage(1), /blocked.*site settings/);
  assert.match(locationErrorMessage(2), /location services/);
  assert.match(locationErrorMessage(3), /too long/);
  assert.match(locationErrorMessage("unsupported"), /can't share/);
  for (const c of [1, 2, 3, "unsupported"] as const) assert.match(locationErrorMessage(c), /city/);
});
