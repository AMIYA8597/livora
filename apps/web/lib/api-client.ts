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
}

let isRefreshing = false;
let refreshSubscribers: ((newToken: string) => void)[] = [];

function onTokenRefreshed(newToken: string) {
  refreshSubscribers.forEach((cb) => cb(newToken));
  refreshSubscribers = [];
}

function addRefreshSubscriber(cb: (newToken: string) => void) {
  refreshSubscribers.push(cb);
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
    const response = await fetch(url, {
      ...customConfig,
      signal: controller.signal,
      headers: {
        ...defaultHeaders,
        ...(headers as Record<string, string>),
      },
    });

    // Check for HTTP 401 Unauthorized to trigger silent token refresh
    if (response.status === 401 && !skipAuthRefresh && typeof window !== "undefined") {
      const refreshToken = localStorage.getItem("flatmate_refresh_token");

      if (refreshToken) {
        if (!isRefreshing) {
          isRefreshing = true;
          try {
            const refreshRes = await fetch(`${API_BASE_URL}/auth/refresh`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ refresh_token: refreshToken }),
            });

            if (refreshRes.ok) {
              const data = await refreshRes.json();
              if (data.access_token) {
                localStorage.setItem("flatmate_access_token", data.access_token);
                if (data.refresh_token) {
                  localStorage.setItem("flatmate_refresh_token", data.refresh_token);
                }
                isRefreshing = false;
                onTokenRefreshed(data.access_token);
                // Replay original call with updated token
                return apiClient<T>(endpoint, {
                  ...options,
                  skipAuthRefresh: true,
                  token: data.access_token,
                });
              }
            }
            throw new Error("Token refresh response did not contain access_token");
          } catch (refreshErr) {
            isRefreshing = false;
            refreshSubscribers = [];
            localStorage.removeItem("flatmate_access_token");
            localStorage.removeItem("flatmate_refresh_token");
            window.dispatchEvent(new CustomEvent("flatmate:auth-expired"));
          }
        } else {
          // If refresh is already in flight, queue this request
          return new Promise<T>((resolve, reject) => {
            addRefreshSubscriber((newToken) => {
              apiClient<T>(endpoint, {
                ...options,
                skipAuthRefresh: true,
                token: newToken,
              })
                .then(resolve)
                .catch(reject);
            });
          });
        }
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
