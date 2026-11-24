"use client";

import type { CityDTO } from "@flatmate/contracts";
import { useApiQuery } from "@/hooks/useApiQuery";

/**
 * The city catalogue (every state and UT capital plus major cities). The API marks it cacheable
 * for an hour, so pages that use it share one download.
 */
export function useCities() {
  const query = useApiQuery<CityDTO[]>("/locations/cities");
  return { cities: query.data ?? [], isLoading: query.isLoading, error: query.error, retry: query.refetch };
}
