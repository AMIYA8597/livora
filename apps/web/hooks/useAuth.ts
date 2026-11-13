"use client";

import { useState, useEffect, useCallback } from "react";
import { UserDTO, AuthTokens } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";

export function useAuth() {
  const [user, setUser] = useState<UserDTO | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchCurrentUser = useCallback(async () => {
    try {
      const token = localStorage.getItem("flatmate_access_token");
      if (!token) {
        setUser(null);
        setIsLoading(false);
        return;
      }
      const data = await apiClient<UserDTO>("/auth/me");
      setUser(data);
    } catch (err) {
      localStorage.removeItem("flatmate_access_token");
      localStorage.removeItem("flatmate_refresh_token");
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCurrentUser();
  }, [fetchCurrentUser]);

  const login = (tokens: AuthTokens, userData: UserDTO) => {
    localStorage.setItem("flatmate_access_token", tokens.access_token);
    localStorage.setItem("flatmate_refresh_token", tokens.refresh_token);
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem("flatmate_access_token");
    localStorage.removeItem("flatmate_refresh_token");
    setUser(null);
    window.location.href = "/";
  };

  return {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    refreshUser: fetchCurrentUser,
  };
}
