/**
 * Saved (favourited) property ids, kept in localStorage and shared by every component through
 * useSyncExternalStore, so a heart toggled on one card updates every other view, including
 * other tabs (via the storage event).
 */
const KEY = "flatmate_saved_properties";
const EMPTY: readonly string[] = Object.freeze([]);
const listeners = new Set<() => void>();

let cachedRaw: string | null = null;
let cachedIds: readonly string[] = EMPTY;

function read(): readonly string[] {
  if (typeof localStorage === "undefined") return EMPTY;
  const raw = localStorage.getItem(KEY);
  if (raw === cachedRaw) return cachedIds;
  cachedRaw = raw;
  try {
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    cachedIds = Array.isArray(parsed) ? Object.freeze(parsed.filter((v): v is string => typeof v === "string")) : EMPTY;
  } catch {
    cachedIds = EMPTY;
  }
  return cachedIds;
}

function write(ids: readonly string[]): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(KEY, JSON.stringify(ids));
  listeners.forEach((l) => l());
}

function onStorage(event: StorageEvent): void {
  if (event.key === KEY || event.key === null) listeners.forEach((l) => l());
}

export function subscribeSaved(listener: () => void): () => void {
  if (listeners.size === 0 && typeof window !== "undefined") window.addEventListener("storage", onStorage);
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && typeof window !== "undefined") window.removeEventListener("storage", onStorage);
  };
}

export const getSavedSnapshot = read;
export const getSavedServerSnapshot = (): readonly string[] => EMPTY;

/** Returns the new saved state for the id. */
export function toggleSaved(id: string): boolean {
  const ids = read();
  const next = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
  write(next);
  return next.includes(id);
}

export function removeSaved(id: string): void {
  write(read().filter((x) => x !== id));
}
