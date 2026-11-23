"use client";

import { useSyncExternalStore } from "react";
import {
  getSavedServerSnapshot,
  getSavedSnapshot,
  removeSaved,
  subscribeSaved,
  toggleSaved,
} from "@/lib/saved-properties";

export function useSavedProperties() {
  const ids = useSyncExternalStore(subscribeSaved, getSavedSnapshot, getSavedServerSnapshot);
  return {
    ids,
    isSaved: (id: string) => ids.includes(id),
    toggle: toggleSaved,
    remove: removeSaved,
  };
}
