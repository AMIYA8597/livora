"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { locationErrorMessage, roundPoint, type NearPoint } from "@/lib/near-me";

export type NearMeStatus = "off" | "asking" | "on" | "error";

/**
 * The visitor's approximate position, asked for only when `ask()` runs (a button tap). It is
 * rounded to ~1 km, kept in memory for this page only, and never written to storage or the URL.
 */
export function useNearMe({ askOnMount = false }: { askOnMount?: boolean } = {}) {
  const [near, setNear] = useState<NearPoint | null>(null);
  const [status, setStatus] = useState<NearMeStatus>("off");
  const [message, setMessage] = useState<string | null>(null);
  const request = useRef(0);

  const ask = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setStatus("error");
      setMessage(locationErrorMessage("unsupported"));
      return;
    }
    const id = ++request.current;
    setStatus("asking");
    setMessage(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (id !== request.current) return; // turned off while asking
        setNear(roundPoint(pos.coords.latitude, pos.coords.longitude));
        setStatus("on");
      },
      (err) => {
        if (id !== request.current) return;
        setNear(null);
        setStatus("error");
        setMessage(locationErrorMessage(err.code));
      },
      // City-block accuracy is enough and answers faster; a position up to 10 minutes old is fine.
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 600_000 },
    );
  }, []);

  // The visitor tapped "Near me" on the previous page: ask once this page is up.
  useEffect(() => {
    if (!askOnMount) return;
    const t = setTimeout(ask, 0);
    return () => clearTimeout(t);
  }, [askOnMount, ask]);

  const clear = useCallback(() => {
    request.current++;
    setNear(null);
    setStatus("off");
    setMessage(null);
  }, []);

  return { near, status, message, ask, clear };
}
