"use client";

import { useState, useEffect, useCallback } from "react";
import { UserDTO, AuthTokens, TokenResponse, UserRole } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";

export function useAuth() {
  const [user, setUser] = useState<UserDTO | null>(null);
  const [roles, setRoles] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchCurrentUser = useCallback(async () => {
    try {
      if (typeof window === "undefined") {
        setIsLoading(false);
        return;
      }
      const token = localStorage.getItem("flatmate_access_token");
      if (!token) {
        setUser(null);
        setRoles([]);
        setIsLoading(false);
        return;
      }

      // Fetch verified user from backend
      const data = await apiClient<UserDTO>("/auth/me");
      setUser(data);

      // Extract stored roles or fallback to user.role
      const storedRoles = localStorage.getItem("flatmate_user_roles");
      if (storedRoles) {
        try {
          setRoles(JSON.parse(storedRoles));
        } catch {
          setRoles(data.roles || [data.role]);
        }
      } else {
        setRoles(data.roles || [data.role]);
      }
    } catch (err) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("flatmate_access_token");
        localStorage.removeItem("flatmate_refresh_token");
        localStorage.removeItem("flatmate_user_roles");
      }
      setUser(null);
      setRoles([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCurrentUser();

    const handleAuthExpired = () => {
      setUser(null);
      setRoles([]);
      setIsLoading(false);
    };

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "flatmate_access_token") {
        fetchCurrentUser();
      }
    };

    if (typeof window !== "undefined") {
      window.addEventListener("flatmate:auth-expired", handleAuthExpired);
      window.addEventListener("storage", handleStorageChange);
    }

    return () => {
      if (typeof window !== "undefined") {
        window.removeEventListener("flatmate:auth-expired", handleAuthExpired);
        window.removeEventListener("storage", handleStorageChange);
      }
    };
  }, [fetchCurrentUser]);

  const login = (tokens: AuthTokens, userData: UserDTO, userRoles?: string[]) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("flatmate_access_token", tokens.access_token);
      localStorage.setItem("flatmate_refresh_token", tokens.refresh_token);
      const effectiveRoles = userRoles && userRoles.length > 0 ? userRoles : (userData.roles || [userData.role]);
      localStorage.setItem("flatmate_user_roles", JSON.stringify(effectiveRoles));
      setRoles(effectiveRoles);
    }
    setUser(userData);
  };

  const logout = async () => {
    try {
      await apiClient("/auth/logout", { method: "POST", skipAuthRefresh: true }).catch(() => {});
    } finally {
      if (typeof window !== "undefined") {
        localStorage.removeItem("flatmate_access_token");
        localStorage.removeItem("flatmate_refresh_token");
        localStorage.removeItem("flatmate_user_roles");
        setUser(null);
        setRoles([]);
        window.location.href = "/";
      }
    }
  };

  const hasRole = (role: string | UserRole): boolean => {
    if (!user) return false;
    if (roles.includes("super_admin") || roles.includes("admin")) return true;
    return roles.includes(role) || user.role === role;
  };

  return {
    user,
    roles,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    refreshUser: fetchCurrentUser,
    hasRole,
    isOwner: hasRole("owner"),
    isSeeker: hasRole("seeker"),
    isAdmin: hasRole("admin") || hasRole("super_admin"),
    isPgOperator: hasRole("pg_operator"),
  };
}
