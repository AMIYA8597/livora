"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client";
import { queryKey, type QueryParams } from "@/lib/query-key";

type Params = QueryParams;

interface QueryResult<T> {
  /** Endpoint + params this result belongs to. */
  key: string | null;
  /** key + refetch counter of the request that produced it. */
  fetchKey: string | null;
  data: T | undefined;
  error: Error | null;
}

export interface UseApiQueryResult<T> {
  data: T | undefined;
  error: Error | null;
  /** True while there is no result yet for the current endpoint/params. */
  isLoading: boolean;
  /** True while a refetch is running and the previous data is still shown. */
  isRefreshing: boolean;
  refetch: () => void;
  /** Update the cached data locally, e.g. after a mutation. */
  setData: (update: T | ((current: T | undefined) => T)) => void;
}

export interface UseApiQueryOptions<T = unknown> {
  /** Treat 404 as "nothing yet": data becomes null and no error is reported. */
  allowNotFound?: boolean;
  /**
   * Data the server already fetched for this exact request (same `queryKey`), used instead of
   * the first fetch. Any later change of endpoint/params, or a refetch, goes to the API.
   */
  initial?: { key: string; data: T };
}

export { queryKey };

/**
 * GET an API endpoint and track loading/error state.
 *
 * Pass `null` as the endpoint to wait (e.g. until the user is signed in). Changing the endpoint
 * or params refetches; responses for an outdated request are dropped, and in-flight requests are
 * aborted on change and unmount. All state updates happen in async callbacks, never
 * synchronously inside the effect.
 */
export function useApiQuery<T>(
  endpoint: string | null,
  params?: Params,
  options?: UseApiQueryOptions<T>,
): UseApiQueryResult<T> {
  const allowNotFound = options?.allowNotFound ?? false;
  const key = endpoint === null ? null : queryKey(endpoint, params);
  const [nonce, setNonce] = useState(0);
  const seeded = options?.initial && key !== null && options.initial.key === key ? options.initial : null;
  const [result, setResult] = useState<QueryResult<T>>(() =>
    seeded
      ? { key: seeded.key, fetchKey: `${seeded.key}#0`, data: seeded.data, error: null }
      : { key: null, fetchKey: null, data: undefined, error: null },
  );
  // The fetch the server already did for us; skipped once.
  const skipFetch = useRef<string | null>(seeded ? `${seeded.key}#0` : null);
  const fetchKey = key === null ? null : `${key}#${nonce}`;

  useEffect(() => {
    if (key === null || fetchKey === null) return;
    if (skipFetch.current === fetchKey) {
      skipFetch.current = null;
      return;
    }
    const [path, query] = JSON.parse(key) as [string, Params | null];
    const controller = new AbortController();
    apiClient<T>(path, { params: query ?? undefined, signal: controller.signal }).then(
      (data) => {
        if (!controller.signal.aborted) setResult({ key, fetchKey, data, error: null });
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        if (allowNotFound && error instanceof ApiError && error.status === 404) {
          setResult({ key, fetchKey, data: null as T, error: null });
          return;
        }
        setResult((prev) => ({
          key,
          fetchKey,
          // Keep showing the last good data for this key if a refetch fails.
          data: prev.key === key ? prev.data : undefined,
          error: error instanceof Error ? error : new Error(String(error)),
        }));
      },
    );
    return () => controller.abort();
  }, [key, fetchKey, allowNotFound]);

  const refetch = useCallback(() => setNonce((n) => n + 1), []);
  const setData = useCallback((update: T | ((current: T | undefined) => T)) => {
    setResult((prev) => ({
      ...prev,
      data: typeof update === "function" ? (update as (current: T | undefined) => T)(prev.data) : update,
    }));
  }, []);

  const sameKey = key !== null && result.key === key;
  return {
    data: sameKey ? result.data : undefined,
    error: sameKey ? result.error : null,
    isLoading: key !== null && !sameKey,
    isRefreshing: sameKey && result.fetchKey !== fetchKey,
    refetch,
    setData,
  };
}
