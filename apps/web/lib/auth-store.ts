/**
 * Single source of truth for the signed-in user.
 *
 * Every `useAuth()` caller subscribes to this one store (via useSyncExternalStore), so the
 * navbar and the page always agree, and `/auth/me` is fetched once rather than per component.
 *
 * Roles come only from the server (`/auth/me` and the login/register response). Roles kept in
 * localStorage are never trusted, so editing storage cannot unlock admin or owner UI.
 *
 * A network failure does not sign the user out: tokens are cleared only when the API answers
 * 401/403. Other failures leave status "error" and the store retries by itself (with backoff,
 * and at once when the browser comes back online or the tab regains focus), so a blip at page
 * load doesn't leave a signed-in user looking signed out until they reload.
 */
import type { AuthTokens, UserDTO } from "@flatmate/contracts";
import { apiClient, ApiError } from "./api-client.ts";
import { forgetPushSubscription } from "./push.ts";

export const ACCESS_TOKEN_KEY = "flatmate_access_token";
export const REFRESH_TOKEN_KEY = "flatmate_refresh_token";
const LEGACY_ROLES_KEY = "flatmate_user_roles";

export type AuthStatus = "loading" | "authenticated" | "anonymous" | "error";

export interface AuthState {
  status: AuthStatus;
  user: UserDTO | null;
  roles: string[];
}

const SERVER_SNAPSHOT: AuthState = Object.freeze({ status: "loading", user: null, roles: [] }) as AuthState;

let state: AuthState = SERVER_SNAPSHOT;
const listeners = new Set<() => void>();
let started = false;
let generation = 0;

const RETRY_BASE_MS = 2_000;
const RETRY_MAX_MS = 30_000;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let retryAttempt = 0;

function cancelRetry(): void {
  if (retryTimer !== null) clearTimeout(retryTimer);
  retryTimer = null;
}

function scheduleRetry(): void {
  cancelRetry();
  const delay = Math.min(RETRY_BASE_MS * 2 ** retryAttempt, RETRY_MAX_MS);
  retryAttempt += 1;
  retryTimer = setTimeout(() => {
    retryTimer = null;
    void refreshAuth();
  }, delay);
  // Never keep a Node test process alive just for this timer.
  (retryTimer as { unref?: () => void }).unref?.();
}

/** Retry now if the last check failed on the network (used for online/focus events). */
function retryIfErrored(): void {
  if (state.status === "error") void refreshAuth();
}

function setState(next: AuthState): void {
  if (next.status !== "error") {
    cancelRetry();
    retryAttempt = 0;
  }
  state = next;
  listeners.forEach((listener) => listener());
}

function rolesOf(user: UserDTO, extra?: string[]): string[] {
  return Array.from(new Set([user.role, ...(user.roles ?? []), ...(extra ?? [])])).sort();
}

function hasStorage(): boolean {
  return typeof localStorage !== "undefined";
}

function clearTokens(): void {
  if (!hasStorage()) return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(LEGACY_ROLES_KEY);
}

/** Re-read the session from the API. Safe to call at any time. */
export async function refreshAuth(): Promise<void> {
  const run = ++generation;
  const token = hasStorage() ? localStorage.getItem(ACCESS_TOKEN_KEY) : null;
  if (!token) {
    setState({ status: "anonymous", user: null, roles: [] });
    return;
  }
  try {
    const user = await apiClient<UserDTO>("/auth/me");
    if (run !== generation) return; // a newer login/logout/refresh won
    setState({ status: "authenticated", user, roles: rolesOf(user) });
  } catch (err) {
    if (run !== generation) return;
    if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
      clearTokens();
      setState({ status: "anonymous", user: null, roles: [] });
    } else {
      setState({ status: "error", user: null, roles: [] });
      scheduleRetry();
    }
  }
}

function start(): void {
  if (started || typeof window === "undefined") return;
  started = true;
  if (hasStorage()) localStorage.removeItem(LEGACY_ROLES_KEY);
  window.addEventListener("flatmate:auth-expired", () => {
    generation++;
    clearTokens();
    setState({ status: "anonymous", user: null, roles: [] });
  });
  // Sign-in / sign-out in another tab.
  window.addEventListener("storage", (event: StorageEvent) => {
    if (event.key === ACCESS_TOKEN_KEY || event.key === null) void refreshAuth();
  });
  window.addEventListener("online", retryIfErrored);
  window.addEventListener("focus", retryIfErrored);
  void refreshAuth();
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  start();
  return () => {
    listeners.delete(listener);
  };
}

export function getSnapshot(): AuthState {
  return state;
}

export function getServerSnapshot(): AuthState {
  return SERVER_SNAPSHOT;
}

/** Store tokens from a login/register response and publish the user immediately. */
export function signIn(tokens: AuthTokens, user: UserDTO, roles?: string[]): void {
  generation++;
  if (hasStorage()) {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  }
  setState({ status: "authenticated", user, roles: rolesOf(user, roles) });
}

export async function signOut(): Promise<void> {
  generation++;
  // Before the token goes: the next person on this browser must not get this account's pushes.
  await forgetPushSubscription().catch(() => undefined);
  await apiClient("/auth/logout", { method: "POST", skipAuthRefresh: true }).catch(() => undefined);
  clearTokens();
  setState({ status: "anonymous", user: null, roles: [] });
}

export function hasRoleIn(current: AuthState, role: string): boolean {
  if (!current.user) return false;
  if (current.roles.includes("super_admin") || current.roles.includes("admin")) return true;
  return current.roles.includes(role);
}

/** Test helper: reset module state between cases. */
export function __resetAuthStoreForTests(): void {
  state = SERVER_SNAPSHOT;
  listeners.clear();
  started = false;
  generation = 0;
  cancelRetry();
  retryAttempt = 0;
}
