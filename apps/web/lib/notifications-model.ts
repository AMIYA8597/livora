/** Pure helpers for the notification centre and Web Push (no imports, so node tests can load it). */

export interface NotificationLike {
  id: string;
  created_at: string;
  is_read: boolean;
  link?: string | null;
}

/** Same-site relative paths only: anything else opens the notification centre instead. */
export function safeHref(link: string | null | undefined): string {
  if (!link || !link.startsWith("/") || link.startsWith("//") || link.includes("\\")) return "/notifications";
  return link;
}

/** Add or replace by id, newest first. */
export function mergeNotification<T extends NotificationLike>(list: readonly T[], incoming: T): T[] {
  return [incoming, ...list.filter((n) => n.id !== incoming.id)].sort((a, b) => b.created_at.localeCompare(a.created_at));
}

/** Combine pages without duplicates, newest first. */
export function appendPage<T extends NotificationLike>(list: readonly T[], page: readonly T[]): T[] {
  const seen = new Set(list.map((n) => n.id));
  return [...list, ...page.filter((n) => !seen.has(n.id))];
}

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/** "Today", "Yesterday", "This week" or "Earlier", in the viewer's local time. */
export function dayGroup(iso: string, now: Date = new Date()): string {
  const days = Math.round((startOfDay(now) - startOfDay(new Date(iso))) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "This week";
  return "Earlier";
}

export function groupByDay<T extends NotificationLike>(list: readonly T[], now: Date = new Date()): { label: string; items: T[] }[] {
  const groups: { label: string; items: T[] }[] = [];
  for (const n of list) {
    const label = dayGroup(n.created_at, now);
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.items.push(n);
    else groups.push({ label, items: [n] });
  }
  return groups;
}

/** "just now", "5m", "3h", "2d", then a short date. */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const seconds = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h`;
  if (seconds < 7 * 86_400) return `${Math.floor(seconds / 86_400)}d`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export const CATEGORY_LABELS: Record<string, { title: string; hint: string }> = {
  messages: { title: "Messages", hint: "New chat messages, when you're not in the app" },
  matches: { title: "Matches and likes", hint: "Mutual matches and new likes" },
  rentals: { title: "Applications and visits", hint: "Applications, decisions and visit requests" },
  account: { title: "Account and billing", hint: "Plan renewals and payment problems" },
};

/** VAPID public key (base64url) to the bytes `PushManager.subscribe` expects. */
export function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}
