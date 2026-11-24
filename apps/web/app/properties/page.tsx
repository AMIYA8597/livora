import { queryKey } from "@/lib/query-key";
import { filtersFromSearch, listingQueryParams } from "@/lib/listing-query";
import { fetchListings } from "@/lib/server-api";
import { PropertiesBrowser } from "./PropertiesBrowser";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/**
 * Listings search. The first page of results is fetched here, so the HTML already carries the
 * listings (and the first photo starts loading straight away); filtering after that happens in
 * the browser.
 */
export default async function PropertiesPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const get = (k: string) => {
    const v = sp[k];
    return Array.isArray(v) ? v[0] : v;
  };
  const { applied, page } = filtersFromSearch(get);
  const params = listingQueryParams(applied, page);
  const data = await fetchListings(params);
  return <PropertiesBrowser initial={data ? { key: queryKey("/properties", params), data } : undefined} />;
}
