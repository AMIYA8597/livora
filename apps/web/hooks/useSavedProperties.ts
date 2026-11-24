"use client";

import { useCallback, useSyncExternalStore } from "react";
import { useAuth } from "@/hooks/useAuth";
import { sendListingSignal } from "@/lib/listing-signals";
import {
  getSavedServerSnapshot,
  getSavedSnapshot,
  removeSaved,
  subscribeSaved,
  toggleSaved,
} from "@/lib/saved-properties";

export function useSavedProperties() {
  const ids = useSyncExternalStore(subscribeSaved, getSavedSnapshot, getSavedServerSnapshot);
  const { isAuthenticated } = useAuth();
  // Saved ids stay on this device; signed-in people also tell the API, for their recommendations.
  const toggle = useCallback((id: string) => {
    const nowSaved = toggleSaved(id);
    if (isAuthenticated) sendListingSignal(id, nowSaved ? "save" : "unsave");
    return nowSaved;
  }, [isAuthenticated]);
  return {
    ids,
    isSaved: (id: string) => ids.includes(id),
    toggle,
    remove: removeSaved,
  };
}
