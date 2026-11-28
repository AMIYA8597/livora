import { test } from "node:test";
import assert from "node:assert/strict";

import { placeLabel } from "../lib/utils.ts";

test("a listing's place names its city once", () => {
  assert.equal(placeLabel("Baner", "Pune"), "Baner, Pune");
  assert.equal(placeLabel("Baner, Pune", "Pune"), "Baner, Pune");
  assert.equal(placeLabel("Salt Lake Sector V, kolkata", "Kolkata"), "Salt Lake Sector V, kolkata");
  assert.equal(placeLabel("Pune Station Road", "Pune"), "Pune Station Road, Pune");
  assert.equal(placeLabel("", "Pune"), "Pune");
  assert.equal(placeLabel("Baner", null), "Baner");
  assert.equal(placeLabel(null, undefined), "");
});
