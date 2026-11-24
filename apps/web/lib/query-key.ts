export type QueryParams = Record<string, string | number | boolean | undefined | null>;

/** The cache key for an endpoint and its params (shared by the server and useApiQuery). */
export function queryKey(endpoint: string, params?: QueryParams): string {
  return JSON.stringify([endpoint, params ?? null]);
}
