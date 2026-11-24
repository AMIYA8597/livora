"use client";

import { useEffect } from "react";

/** Registers the service worker for everyone (not only people who turn on push), so the
 *  installed app shows the offline page instead of the browser's error when there's no
 *  network. The worker caches nothing else; see public/sw.js. */
export function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const register = () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
        // Not fatal: the site works without it (private windows, blocked storage).
      });
    };
    if (document.readyState === "complete") register();
    else {
      window.addEventListener("load", register, { once: true });
      return () => window.removeEventListener("load", register);
    }
  }, []);
  return null;
}
