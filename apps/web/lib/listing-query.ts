/**
 * The listings search request, built the same way on the server (first render) and in the
 * browser, so the server's results can stand in for the browser's first fetch.
 */
export const LISTINGS_PAGE_SIZE = 9;

/** Server-side orders (the API's `sort`). "recommended" is ranked for the signed-in person. */
export const LISTING_SORTS = ["recommended", "nearest", "newest", "price_asc", "price_desc"] as const;
export type ListingSort = (typeof LISTING_SORTS)[number];
export const DEFAULT_SORT: ListingSort = "recommended";

export function parseSort(value: string | null | undefined): ListingSort {
  return (LISTING_SORTS as readonly string[]).includes(value ?? "") ? (value as ListingSort) : DEFAULT_SORT;
}

export interface AppliedFilters {
  q: string;
  city: string;
  locality: string;
  minRent: string;
  maxRent: string;
  category: string;
  configuration: string;
  furnishing: string;
}

type Get = (key: string) => string | null | undefined;

export function filtersFromSearch(get: Get): { applied: AppliedFilters; page: number; sort: ListingSort } {
  const v = (k: string) => get(k) || "";
  const page = Number(get("page"));
  return {
    applied: {
      q: v("q"),
      city: v("city"),
      locality: v("locality"),
      minRent: v("min_rent"),
      maxRent: v("max_rent"),
      category: v("category"),
      configuration: v("config"),
      furnishing: v("furnishing"),
    },
    page: Number.isInteger(page) && page > 0 ? page : 1,
    sort: parseSort(get("sort")),
  };
}

export function listingQueryParams(applied: AppliedFilters, page: number, sort?: ListingSort) {
  return {
    sort,
    limit: LISTINGS_PAGE_SIZE,
    offset: (page - 1) * LISTINGS_PAGE_SIZE,
    // Free text is matched by meaning as well as words (hybrid search) and ordered by relevance.
    q: applied.q.trim() || undefined,
    city: applied.city.trim() || undefined,
    locality: applied.locality.trim() || undefined,
    furnishing_status: applied.furnishing || undefined,
    min_rent: applied.minRent ? Number(applied.minRent) : undefined,
    max_rent: applied.maxRent ? Number(applied.maxRent) : undefined,
    property_category: applied.category || undefined,
    configuration: applied.configuration || undefined,
  };
}

/** Query string for a server-side fetch: undefined values left out, like the API client does. */
export function toQueryString(params: Record<string, string | number | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null) sp.append(k, String(v));
  return sp.toString();
}
