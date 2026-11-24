// Server-side only: imported by server components (page metadata, sitemap).
import type { PropertyDTO } from "@flatmate/contracts";
import { toQueryString } from "./listing-query";
import { serverApiBase } from "./site";

/** Listings change rarely; pages and previews are refreshed at most every 5 minutes. */
export const LISTING_REVALIDATE_SECONDS = 300;

export type PublicListing =
  | { kind: "found"; property: PropertyDTO }
  | { kind: "missing" }
  | { kind: "unavailable" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** A listing as an anonymous visitor sees it (published only). Never throws. */
export async function fetchPublicListing(id: string): Promise<PublicListing> {
  if (!UUID.test(id)) return { kind: "missing" };
  try {
    const res = await fetch(`${serverApiBase()}/properties/${id}`, {
      headers: { Accept: "application/json" },
      next: { revalidate: LISTING_REVALIDATE_SECONDS, tags: [`property:${id}`] },
      signal: AbortSignal.timeout(5000),
    });
    if (res.status === 404 || res.status === 422) return { kind: "missing" };
    if (!res.ok) return { kind: "unavailable" };
    return { kind: "found", property: (await res.json()) as PropertyDTO };
  } catch {
    return { kind: "unavailable" };
  }
}

/** Published listing ids for the sitemap, newest first. Empty when the API can't be reached. */
export async function fetchListingIdsForSitemap(max = 1000): Promise<{ id: string; updated?: string }[]> {
  const out: { id: string; updated?: string }[] = [];
  try {
    for (let offset = 0; offset < max; offset += 100) {
      const res = await fetch(`${serverApiBase()}/properties/?limit=100&offset=${offset}`, {
        headers: { Accept: "application/json" },
        next: { revalidate: 3600 },
        signal: AbortSignal.timeout(8000),
      });
      if (!res.ok) break;
      const page = (await res.json()) as (PropertyDTO & { updated_at?: string })[];
      for (const p of page) out.push({ id: p.id, updated: p.updated_at });
      if (page.length < 100) break;
    }
  } catch {
    /* the sitemap still lists the static pages */
  }
  return out;
}

/** One page of public listings for the search page's first render; null if the API failed. */
export async function fetchListings(
  params: Record<string, string | number | undefined>,
): Promise<PropertyDTO[] | null> {
  try {
    const res = await fetch(`${serverApiBase()}/properties?${toQueryString(params)}`, {
      headers: { Accept: "application/json" },
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(5000),
    });
    return res.ok ? ((await res.json()) as PropertyDTO[]) : null;
  } catch {
    return null;
  }
}
