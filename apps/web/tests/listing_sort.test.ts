import test from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_SORT, filtersFromSearch, listingQueryParams, parseSort, toQueryString } from "../lib/listing-query.ts";

test("sort: recommended by default, and only known orders reach the API", () => {
  assert.equal(DEFAULT_SORT, "recommended");
  assert.equal(parseSort(undefined), "recommended");
  assert.equal(parseSort("price_asc"), "price_asc");
  assert.equal(parseSort("nearest"), "nearest");
  assert.equal(parseSort("random"), "recommended");
  assert.equal(filtersFromSearch(() => null).sort, "recommended");
  assert.equal(filtersFromSearch((k) => (k === "sort" ? "price_desc" : null)).sort, "price_desc");
});

test("sort: sent to the API, so price order covers every page", () => {
  const { applied } = filtersFromSearch(() => null);
  assert.equal(toQueryString(listingQueryParams(applied, 2, "price_asc")), "sort=price_asc&limit=9&offset=9");
  assert.equal(toQueryString(listingQueryParams(applied, 1)), "limit=9&offset=0");
});
