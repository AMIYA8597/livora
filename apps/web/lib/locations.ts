/**
 * The city catalogue from GET /locations/cities (every state and UT capital plus major cities):
 * picking, grouping and matching names. Pure, so it is unit-tested with `node --test`.
 */
import type { CityDTO } from "@flatmate/contracts";

const key = (name: string) => name.trim().replace(/\s+/g, " ").toLowerCase();

/** The catalogue city a typed name refers to (its name, slug or another name), if any. */
export function findCity(cities: readonly CityDTO[], name: string): CityDTO | undefined {
  const k = key(name);
  if (!k) return undefined;
  return cities.find(
    (c) => key(c.name) === k || key(c.slug.replace(/-/g, " ")) === k || c.aliases.some((a) => key(a) === k),
  );
}

/** The big rental markets, for quick-pick chips. */
export function popularCities(cities: readonly CityDTO[]): CityDTO[] {
  return cities.filter((c) => c.tier === 1).sort((a, b) => a.name.localeCompare(b.name));
}

export interface CityGroup {
  label: string;
  cities: CityDTO[];
}

/** Popular cities first, then every city grouped under its state or union territory. */
export function cityGroups(cities: readonly CityDTO[]): CityGroup[] {
  const byState = new Map<string, CityDTO[]>();
  for (const c of cities) {
    const label = c.state_kind === "union_territory" ? `${c.state} (UT)` : c.state;
    byState.set(label, [...(byState.get(label) ?? []), c]);
  }
  const states = Array.from(byState.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([label, list]) => ({ label, cities: list.sort((a, b) => a.name.localeCompare(b.name)) }));
  const popular = popularCities(cities);
  return popular.length ? [{ label: "Popular", cities: popular }, ...states] : states;
}

/** Every name worth suggesting in a free-text city box: official names, then other names. */
export function citySuggestions(cities: readonly CityDTO[]): string[] {
  const names = cities.map((c) => c.name).sort((a, b) => a.localeCompare(b));
  const aliases = cities.flatMap((c) => c.aliases).sort((a, b) => a.localeCompare(b));
  return Array.from(new Set([...names, ...aliases]));
}

/** "Bengaluru, Karnataka" / "Leh, Ladakh". */
export function cityLabel(c: CityDTO): string {
  return `${c.name}, ${c.state}`;
}
