"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { NotificationDTO } from "@flatmate/contracts";
import { Bell } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useApiQuery } from "@/hooks/useApiQuery";
import { useSocket } from "@/hooks/useSocket";
import { syncPushSubscription } from "@/lib/push";
import { mergeNotification, safeHref, timeAgo } from "@/lib/notifications-model";

/** Other parts of the app (the notification centre) announce read-state changes with this event. */
export const NOTIFICATIONS_CHANGED = "flatmate:notifications-changed";

/**
 * The bell: a live unread count (socket `notification.created`, refetched after reconnects and
 * when the centre changes anything) and the latest few notifications. Clicking one marks it
 * read and opens its page.
 */
export function NotificationBell() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationDTO[] | null>(null);
  const countQuery = useApiQuery<{ unread_count: number }>("/notifications/unread-count");
  const { refetch: refetchCount, setData: setCount } = countQuery;
  const unread = countQuery.data?.unread_count ?? 0;
  const setUnread = useCallback(
    (next: (count: number) => number) => setCount((prev) => ({ unread_count: next(prev?.unread_count ?? 0) })),
    [setCount],
  );
  const ref = useRef<HTMLDivElement>(null);


  const openRef = useRef(false);
  useEffect(() => {
    openRef.current = open;
  }, [open]);

  const loadLatest = useCallback(async () => {
    try {
      setItems(await apiClient<NotificationDTO[]>("/notifications/?limit=6"));
    } catch {
      setItems((prev) => prev ?? []);
    }
  }, []);

  /** Something changed elsewhere (another page, a reconnect): reload now if open, else on next open. */
  const invalidate = useCallback(() => {
    refetchCount();
    if (openRef.current) void loadLatest();
    else setItems(null);
  }, [refetchCount, loadLatest]);

  useEffect(() => {
    void syncPushSubscription().catch(() => undefined);
    window.addEventListener(NOTIFICATIONS_CHANGED, invalidate);
    return () => window.removeEventListener(NOTIFICATIONS_CHANGED, invalidate);
  }, [invalidate]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const callbacks = useMemo(
    () => ({
      onNotificationCreated: (raw: unknown) => {
        const n = raw as NotificationDTO;
        if (!n?.id) return;
        setUnread((c) => c + 1);
        setItems((prev) => (prev ? mergeNotification(prev, n).slice(0, 6) : prev));
      },
      onReconnected: invalidate,
    }),
    [invalidate, setUnread],
  );
  useSocket(callbacks);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && items === null) void loadLatest();
  };

  const openItem = async (n: NotificationDTO) => {
    setOpen(false);
    if (!n.is_read) {
      setItems((prev) => prev?.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)) ?? prev);
      setUnread((c) => Math.max(0, c - 1));
      void apiClient(`/notifications/${n.id}/read`, { method: "PATCH" }).then(
        () => window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED)),
        () => undefined,
      );
    }
    router.push(safeHref(n.link));
  };

  const markAll = async () => {
    setUnread(() => 0);
    setItems((prev) => prev?.map((x) => ({ ...x, is_read: true })) ?? prev);
    await apiClient("/notifications/read-all", { method: "POST" }).catch(() => undefined);
    window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED));
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={toggle}
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        aria-haspopup="true"
        className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] text-charcoal-light hover:text-forest hover:bg-slate-100 rounded-xl transition-colors relative"
      >
        <Bell className="w-5 h-5" />
        {unread > 0 && (
          <span className="absolute top-1 right-1 min-w-[18px] h-[18px] bg-rose-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed inset-x-2 top-16 sm:absolute sm:inset-x-auto sm:top-auto sm:right-0 sm:mt-2 sm:w-96 bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-150">
          <div className="px-4 py-2 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-charcoal">Notifications</span>
            {unread > 0 && (
              <button
                type="button"
                onClick={markAll}
                className="min-h-[44px] text-[11px] font-semibold text-secondary-green hover:underline"
              >
                Mark all as read
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
            {items === null ? (
              <div className="p-6 text-center text-xs text-charcoal-muted">Loading…</div>
            ) : items.length === 0 ? (
              <div className="p-6 text-center text-xs text-charcoal-muted">You&apos;re all caught up.</div>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => openItem(n)}
                  className={`w-full text-left p-3.5 hover:bg-slate-50 transition-colors flex items-start gap-2.5 ${
                    !n.is_read ? "bg-pale-green/15" : ""
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${n.is_read ? "bg-transparent" : "bg-forest"}`}
                  />
                  <span className="flex-1 min-w-0 text-xs">
                    <span className="flex items-start justify-between gap-2">
                      <span className="font-semibold text-charcoal">{n.title}</span>
                      <span className="text-[10px] text-charcoal-muted shrink-0">{timeAgo(n.created_at)}</span>
                    </span>
                    <span className="block text-slate-500 mt-0.5 line-clamp-2">{n.body}</span>
                    {!n.is_read && <span className="sr-only">Unread</span>}
                  </span>
                </button>
              ))
            )}
          </div>
          <Link
            href="/notifications"
            onClick={() => setOpen(false)}
            className="block py-3 text-center text-xs font-semibold text-secondary-green hover:bg-slate-50 border-t border-slate-100"
          >
            See all notifications
          </Link>
        </div>
      )}
    </div>
  );
}
