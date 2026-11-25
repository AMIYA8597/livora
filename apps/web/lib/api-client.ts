/**
 * Production-Grade Centralized API Client
 *
 * Capabilities:
 * - Configurable API base URL via NEXT_PUBLIC_API_URL
 * - Strongly-typed requests and generic response mapping
 * - Automatic Authorization header with Supabase/JWT tokens
 * - Secure token handling (no secret leakage, zero token logging)
 * - Automatic Request Timeout & Cancellation via AbortController
 * - RFC 7807 Problem Details error parsing
 * - Automatic 401 Token Refresh & transparent request retry
 * - Zero service-role keys in client code
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * The request never got an HTTP answer: offline, DNS/CORS failure, server down, or timeout.
 * Kept separate from ApiError so callers (e.g. the auth store) never mistake it for a 401.
 */
export class NetworkError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "NetworkError";
  }
}

export class ApiError extends Error {
  status: number;
  title: string;
  detail: string;
  errorCode: string;
  instance?: string;
  invalidParams?: Array<{ name?: string; reason?: string; loc?: string[]; msg?: string }>;
  requestId?: string;
  raw?: any;

  constructor(data: {
    status: number;
    title?: string;
    detail?: string;
    errorCode?: string;
    instance?: string;
    invalidParams?: any[];
    requestId?: string;
    raw?: any;
  }) {
    const message = data.detail || data.title || `API error: ${data.status}`;
    super(message);
    this.name = "ApiError";
    this.status = data.status;
    this.title = data.title || `HTTP ${data.status}`;
    this.detail = message;
    this.errorCode = data.errorCode || "API_ERROR";
    this.instance = data.instance;
    this.invalidParams = data.invalidParams;
    this.requestId = data.requestId;
    this.raw = data.raw;
  }
}

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
  timeoutMs?: number;
  skipAuthRefresh?: boolean;
  token?: string | null;
  /** Internal: how many times this request was already retried because the server was busy. */
  busyAttempt?: number;
}

/** Retries after a "busy" 503 before the error is shown. */
export const BUSY_RETRIES = 2;
const MAX_BUSY_WAIT_MS = 5000;

/**
 * How long to wait before retrying a 503 the server sent because it was busy, or null to give up.
 *
 * SERVER_BUSY means the request was refused before any work, so any method may retry.
 * SERVICE_BUSY (the database was out of connections) is retried only for reads: a write may
 * have got partway. Waits Retry-After (capped), with jitter so clients don't return together.
 */
export function busyRetryDelayMs(
  method: string,
  status: number,
  errorCode: string | undefined,
  retryAfter: string | null,
  attempt: number,
  random: () => number = Math.random,
): number | null {
  if (status !== 503 || attempt >= BUSY_RETRIES) return null;
  const read = ["GET", "HEAD"].includes(method.toUpperCase());
  if (errorCode !== "SERVER_BUSY" && !(errorCode === "SERVICE_BUSY" && read)) return null;
  const seconds = Number(retryAfter);
  const base = Number.isFinite(seconds) && seconds > 0 ? seconds * 1000 : 1000;
  return Math.round(Math.min(base, MAX_BUSY_WAIT_MS) * (0.5 + random()));
}

function wait(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason);
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(signal.reason);
    }, { once: true });
  });
}

let refreshInFlight: Promise<string | null> | null = null;

/**
 * Exchange the refresh token for a new access token. Concurrent callers share one request.
 *
 * Resolves to the new access token, or null when there is no session or the server rejected the
 * refresh token (the session is then cleared and `flatmate:auth-expired` fires). A network failure
 * rejects with NetworkError and keeps the session: being offline must not sign anyone out.
 */
export function refreshAccessToken(): Promise<string | null> {
  if (typeof window === "undefined") return Promise.resolve(null);
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    const refreshToken = localStorage.getItem("flatmate_refresh_token");
    if (!refreshToken) return null;
    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch (err) {
      throw new NetworkError("Can't reach Flatmate right now. Check your connection and try again.", { cause: err });
    }
    const data = res.ok ? await res.json().catch(() => null) : null;
    if (data?.access_token) {
      localStorage.setItem("flatmate_access_token", data.access_token);
      if (data.refresh_token) localStorage.setItem("flatmate_refresh_token", data.refresh_token);
      return data.access_token as string;
    }
    if (res.status >= 500) {
      // The server is having trouble; that says nothing about the session.
      throw new ApiError({ status: res.status, detail: "Couldn't renew your session. Please try again." });
    }
    localStorage.removeItem("flatmate_access_token");
    localStorage.removeItem("flatmate_refresh_token");
    window.dispatchEvent(new CustomEvent("flatmate:auth-expired"));
    return null;
  })().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    params,
    headers,
    timeoutMs = 15000,
    skipAuthRefresh = false,
    token: explicitToken,
    signal: callerSignal,
    busyAttempt = 0,
    ...customConfig
  } = options;

  // Build complete URL with search parameters
  let url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null) {
        searchParams.append(key, String(val));
      }
    });
    const qs = searchParams.toString();
    if (qs) {
      url += `${url.includes("?") ? "&" : "?"}${qs}`;
    }
  }

  // Token resolution (Explicit -> localStorage -> null)
  let token = explicitToken;
  if (!token && typeof window !== "undefined") {
    token = localStorage.getItem("flatmate_access_token");
  }

  const clientRequestId =
    (headers as Record<string, string>)?.[ "X-Request-ID" ] ||
    `req-${Math.random().toString(36).substring(2, 10)}`;

  const defaultHeaders: Record<string, string> = {
    "Accept": "application/json, application/problem+json",
    "X-Request-ID": clientRequestId,
  };

  // Only add Content-Type if we have a body and it is not FormData
  if (customConfig.body && !(customConfig.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  if (token) {
    defaultHeaders["Authorization"] = `Bearer ${token}`;
  }

  // Timeout & Abort management
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort(new Error(`Request timed out after ${timeoutMs}ms`));
  }, timeoutMs);

  if (callerSignal) {
    callerSignal.addEventListener("abort", () => controller.abort(callerSignal.reason));
  }

  try {
    let response: Response;
    try {
      response = await fetch(url, {
        ...customConfig,
        signal: controller.signal,
        headers: {
          ...defaultHeaders,
          ...(headers as Record<string, string>),
        },
      });
    } catch (err) {
      // A caller cancelling its own request is not a network problem; pass it through.
      if (callerSignal?.aborted) throw err;
      // Browsers reject with a bare "Failed to fetch" TypeError; say something a person can act on.
      const timedOut = controller.signal.aborted;
      throw new NetworkError(
        timedOut
          ? "The server took too long to respond. Please try again."
          : "Can't reach Flatmate right now. Check your connection and try again.",
        { cause: err },
      );
    }

    // A 401 means the access token expired: renew it once and replay the request.
    if (response.status === 401 && !skipAuthRefresh && typeof window !== "undefined") {
      const newToken = await refreshAccessToken();
      if (newToken) {
        return apiClient<T>(endpoint, { ...options, skipAuthRefresh: true, token: newToken });
      }
    }

    if (!response.ok) {
      const requestId = response.headers.get("X-Request-ID") || undefined;
      let errorData: any = {};
      try {
        errorData = await response.json();
      } catch {
        errorData = { detail: response.statusText };
      }

      // The server was too busy and said when to come back: wait and try again, quietly.
      const delay = busyRetryDelayMs(
        customConfig.method || "GET", response.status, errorData.error_code,
        response.headers.get("Retry-After"), busyAttempt,
      );
      if (delay !== null) {
        clearTimeout(timeoutId);
        await wait(delay, callerSignal);
        return apiClient<T>(endpoint, { ...options, busyAttempt: busyAttempt + 1 });
      }

      // RFC 7807 Problem Details parsing:
      // Typically: { type, title, status, detail, error_code, invalid_params, instance }
      throw new ApiError({
        status: response.status,
        title: errorData.title || `Error ${response.status}`,
        detail: errorData.detail || errorData.message || response.statusText,
        errorCode: errorData.error_code || (errorData.title ? errorData.title.toUpperCase().replace(/\s+/g, "_") : "API_ERROR"),
        instance: errorData.instance,
        invalidParams: errorData.invalid_params || errorData.detail?.errors,
        requestId,
        raw: errorData,
      });
    }

    // 204 No Content
    if (response.status === 204) {
      return null as unknown as T;
    }

    return (await response.json()) as T;
  } finally {
    clearTimeout(timeoutId);
  }
}

apiClient.get = <T>(endpoint: string, options?: RequestOptions) =>
  apiClient<T>(endpoint, { ...options, method: "GET" });

apiClient.post = <T>(endpoint: string, body?: any, options?: RequestOptions) =>
  apiClient<T>(endpoint, {
    ...options,
    method: "POST",
    body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
  });

apiClient.put = <T>(endpoint: string, body?: any, options?: RequestOptions) =>
  apiClient<T>(endpoint, {
    ...options,
    method: "PUT",
    body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
  });

apiClient.patch = <T>(endpoint: string, body?: any, options?: RequestOptions) =>
  apiClient<T>(endpoint, {
    ...options,
    method: "PATCH",
    body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
  });

apiClient.delete = <T>(endpoint: string, options?: RequestOptions) =>
  apiClient<T>(endpoint, { ...options, method: "DELETE" });

apiClient.upload = <T>(endpoint: string, formData: FormData, options?: RequestOptions) =>
  apiClient<T>(endpoint, { ...options, method: "POST", body: formData });
