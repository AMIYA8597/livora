"use client";

import { useState, useEffect } from "react";
import { FlatmateMatchRecommendation } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";

export function useMatches(limit = 10) {
  const [matches, setMatches] = useState<FlatmateMatchRecommendation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadMatches() {
      try {
        setIsLoading(true);
        const data = await apiClient<FlatmateMatchRecommendation[]>("/matching/recommendations", {
          params: { limit },
        });
        setMatches(data);
      } catch (err: any) {
        setError(err.message || "Failed to load matches");
      } finally {
        setIsLoading(false);
      }
    }
    loadMatches();
  }, [limit]);

  return { matches, isLoading, error };
}
