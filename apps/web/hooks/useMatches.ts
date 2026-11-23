"use client";

import { FlatmateMatchRecommendation } from "@flatmate/contracts";
import { useApiQuery } from "@/hooks/useApiQuery";
import { useAuth } from "@/hooks/useAuth";

/** Match recommendations for the signed-in user (nothing is requested while signed out). */
export function useMatches(limit = 10) {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const query = useApiQuery<FlatmateMatchRecommendation[]>(
    isAuthenticated ? "/matching/recommendations" : null,
    { limit },
  );
  return {
    matches: query.data ?? [],
    isLoading: authLoading || query.isLoading,
    error: query.error ? query.error.message || "Failed to load matches" : null,
    refetch: query.refetch,
  };
}
