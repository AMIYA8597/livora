import test from "node:test";
import assert from "node:assert";
import type { CityDTO } from "@flatmate/contracts";
import { cityGroups, cityLabel, citySuggestions, findCity, popularCities } from "../lib/locations.ts";

const city = (slug: string, name: string, state: string, extra: Partial<CityDTO> = {}): CityDTO => ({
  slug, name, state, state_code: state.slice(0, 2).toUpperCase(), state_kind: "state", is_capital: true,
  tier: 2, latitude: 20, longitude: 78, aliases: [], ...extra,
});

const CITIES: CityDTO[] = [
  city("bengaluru", "Bengaluru", "Karnataka", { tier: 1, aliases: ["Bangalore"] }),
  city("pune", "Pune", "Maharashtra", { tier: 1, is_capital: false, aliases: ["Poona"] }),
  city("mumbai", "Mumbai", "Maharashtra", { tier: 1, aliases: ["Bombay"] }),
  city("new-delhi", "New Delhi", "Delhi", { tier: 1, state_kind: "union_territory", aliases: ["Delhi", "Delhi NCR"] }),
  city("leh", "Leh", "Ladakh", { state_kind: "union_territory" }),
  city("shimla", "Shimla", "Himachal Pradesh"),
];

test("any name of a city finds it", () => {
  assert.strictEqual(findCity(CITIES, "Bangalore")?.slug, "bengaluru");
  assert.strictEqual(findCity(CITIES, "  delhi   ncr ")?.slug, "new-delhi");
  assert.strictEqual(findCity(CITIES, "new delhi")?.slug, "new-delhi");
  assert.strictEqual(findCity(CITIES, "SHIMLA")?.slug, "shimla");
  assert.strictEqual(findCity(CITIES, "Beng"), undefined);
  assert.strictEqual(findCity(CITIES, ""), undefined);
});

test("popular cities first, then every state and UT in order", () => {
  assert.deepStrictEqual(popularCities(CITIES).map((c) => c.name), ["Bengaluru", "Mumbai", "New Delhi", "Pune"]);
  const groups = cityGroups(CITIES);
  assert.deepStrictEqual(groups.map((g) => g.label), [
    "Popular", "Delhi (UT)", "Himachal Pradesh", "Karnataka", "Ladakh (UT)", "Maharashtra",
  ]);
  assert.deepStrictEqual(groups.find((g) => g.label === "Maharashtra")!.cities.map((c) => c.name), ["Mumbai", "Pune"]);
  assert.deepStrictEqual(cityGroups([]), []);
});

test("suggestions offer official names, then the other names people type", () => {
  const s = citySuggestions(CITIES);
  assert.deepStrictEqual(s.slice(0, 6), ["Bengaluru", "Leh", "Mumbai", "New Delhi", "Pune", "Shimla"]);
  assert.ok(s.includes("Bangalore") && s.includes("Delhi NCR"));
  assert.strictEqual(new Set(s).size, s.length);
  assert.strictEqual(cityLabel(CITIES[4]), "Leh, Ladakh");
});
