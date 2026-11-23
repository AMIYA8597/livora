import { test } from "node:test";
import assert from "node:assert/strict";
import { extractPropertyId } from "../lib/listing-link.ts";

const ID = "27ea85e2-60b2-4f44-8ad1-85d113b1876d";

test("listing link: full URL, path, bare ID and upper case all resolve to the ID", () => {
  assert.equal(extractPropertyId(`https://flatmate.app/properties/${ID}?from=share`), ID);
  assert.equal(extractPropertyId(`/properties/${ID}`), ID);
  assert.equal(extractPropertyId(`  ${ID}  `), ID);
  assert.equal(extractPropertyId(ID.toUpperCase()), ID);
});

test("listing link: text without an ID is rejected", () => {
  assert.equal(extractPropertyId("https://flatmate.app/properties/"), null);
  assert.equal(extractPropertyId("2BHK in HSR"), null);
  assert.equal(extractPropertyId(""), null);
});
