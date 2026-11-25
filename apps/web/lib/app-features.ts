"use client";

import { useEffect, useState } from "react";
import { apiClient } from "./api-client";
import { FEATURES_IF_UNKNOWN, featuresFrom, type AppFeatures } from "./app-features-model";

export * from "./app-features-model";

// One request per page load, shared by every component that asks.
let pending: Promise<AppFeatures> | null = null;

export function loadAppFeatures(): Promise<AppFeatures> {
  if (!pending) {
    pending = apiClient<unknown>("/meta/app-config")
      .then(featuresFrom)
      .catch(() => {
        pending = null; // ask again next time
        return FEATURES_IF_UNKNOWN;
      });
  }
  return pending;
}

/** The API's optional features, or null until known (render nothing optional until then, so a
 *  turned-off feature never flashes on screen). */
export function useAppFeatures(): AppFeatures | null {
  const [features, setFeatures] = useState<AppFeatures | null>(null);
  useEffect(() => {
    let alive = true;
    void loadAppFeatures().then((f) => {
      if (alive) setFeatures(f);
    });
    return () => {
      alive = false;
    };
  }, []);
  return features;
}
