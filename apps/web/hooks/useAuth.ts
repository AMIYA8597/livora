"use client";

import { useCallback, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import type { AuthTokens, UserDTO, UserRole } from "@flatmate/contracts";
import {
  getServerSnapshot,
  getSnapshot,
  hasRoleIn,
  refreshAuth,
  signIn,
  signOut,
  subscribe,
} from "@/lib/auth-store";
import { isStaffRoles } from "@/lib/staff-access";

/**
 * The signed-in user, shared by every component (see lib/auth-store.ts).
 * `isLoading` is true until the session has been checked once.
 */
export function useAuth() {
  const state = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const router = useRouter();

  const login = useCallback((tokens: AuthTokens, userData: UserDTO, userRoles?: string[]) => {
    signIn(tokens, userData, userRoles);
  }, []);

  const logout = useCallback(async () => {
    await signOut();
    router.replace("/");
  }, [router]);

  const hasRole = (role: string | UserRole): boolean => hasRoleIn(state, role);

  return {
    user: state.user,
    roles: state.roles,
    status: state.status,
    isAuthenticated: state.status === "authenticated",
    isLoading: state.status === "loading",
    login,
    logout,
    refreshUser: refreshAuth,
    hasRole,
    isOwner: hasRole("owner"),
    /** Owners, PG operators and verified brokers: may list homes and use the listings dashboard. */
    canList: hasRole("owner") || hasRole("pg_operator") || hasRole("broker"),
    isSeeker: hasRole("seeker"),
    isAdmin: hasRole("admin") || hasRole("super_admin"),
    /** Moderators and admins: may open the admin console (see lib/staff-access.ts). */
    isStaff: isStaffRoles(state.roles),
    isPgOperator: hasRole("pg_operator"),
  };
}
