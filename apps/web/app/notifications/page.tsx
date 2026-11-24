"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { NotificationDTO } from "@flatmate/contracts";
import { Button, Card, Skeleton, Tabs } from "@flatmate/ui";
import { Bell, CalendarCheck, CreditCard, Heart, MessageSquare } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useSocket } from "@/hooks/useSocket";
import { apiClient } from "@/lib/api-client";
import { loginHref } from "@/lib/navigation";
import { InlineNotice } from "@/components/states/InlineNotice";
import { NOTIFICATIONS_CHANGED } from "@/components/NotificationBell";
import { PushSettings } from "@/features/notifications/PushSettings";
import { appendPage, groupByDay, mergeNotification, safeHref, timeAgo } from "@/lib/notifications-model";

const PAGE = 20;
const ICONS: Record<string, typeof Bell> = {
  messages: MessageSquare,
  matches: Heart,
  rentals: CalendarCheck,
  account: CreditCard,
};

type Filter = "all" | "unread";

function announce() {
  window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED));
}

export default function NotificationsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [filter, setFilter] = useState<Filter>("all");
  const [items, setItems] = useState<NotificationDTO[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback(
    async (before?: string) => {
      const params = new URLSearchParams({ limit: String(PAGE) });
      if (filter === "unread") params.set("unread_only", "true");
      if (before) params.set("before", before);
      return apiClient<NotificationDTO[]>(`/notifications/?${params}`);
    },
    [filter],
  );

  useEffect(() => {
    if (!isAuthenticated) return;
    let live = true;
    const load = () =>
      fetchPage()
        .then((page) => {
          if (!live) return;
          setItems(page);
          setHasMore(page.length === PAGE);
          setError(null);
        })
        .catch((err) => live && setError(err instanceof Error ? err.message : "Couldn't load notifications."));
    void load();
    // The bell marked something read: show the same state here.
    window.addEventListener(NOTIFICATIONS_CHANGED, load);
    return () => {
      live = false;
      window.removeEventListener(NOTIFICATIONS_CHANGED, load);
    };
  }, [isAuthenticated, fetchPage]);

  const callbacks = useMemo(
    () => ({
      onNotificationCreated: (raw: unknown) => {
        const n = raw as NotificationDTO;
        if (n?.id) setItems((prev) => (prev ? mergeNotification(prev, n) : prev));
      },
    }),
    [],
  );
  useSocket(callbacks);

  const loadMore = async () => {
    if (!items?.length) return;
    setLoadingMore(true);
    try {
      const page = await fetchPage(items[items.length - 1].created_at);
      setItems((prev) => appendPage(prev ?? [], page));
      setHasMore(page.length === PAGE);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load more.");
    } finally {
      setLoadingMore(false);
    }
  };

  const open = (n: NotificationDTO) => {
    if (!n.is_read) {
      setItems((prev) => prev?.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)) ?? prev);
      void apiClient(`/notifications/${n.id}/read`, { method: "PATCH" }).then(announce, () => undefined);
    }
    router.push(safeHref(n.link));
  };

  const markAll = async () => {
    setItems((prev) => (filter === "unread" ? [] : prev?.map((x) => ({ ...x, is_read: true })) ?? prev));
    await apiClient("/notifications/read-all", { method: "POST" }).catch(() => undefined);
    announce();
  };

  if (!authLoading && !isAuthenticated) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center space-y-4">
        <h1 className="text-2xl font-bold text-charcoal">Notifications</h1>
        <p className="text-sm text-charcoal-muted">Sign in to see your notifications.</p>
        <Button variant="primary" onClick={() => router.push(loginHref("/notifications"))}>Sign in</Button>
      </div>
    );
  }

  const hasUnread = items?.some((n) => !n.is_read);
  const groups = groupByDay(items ?? []);

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8 space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-extrabold text-charcoal tracking-tight">Notifications</h1>
        {hasUnread && (
          <Button variant="ghost" size="sm" onClick={markAll} className="min-h-[44px]">
            Mark all as read
          </Button>
        )}
      </div>

      <PushSettings />

      <Tabs
        tabs={[
          { id: "all", label: "All" },
          { id: "unread", label: "Unread" },
        ]}
        activeTab={filter}
        onChange={(id) => {
          setFilter(id as Filter);
          setItems(null);
        }}
      />

      {error && <InlineNotice tone="error">{error}</InlineNotice>}

      {items === null && !error ? (
        <div className="space-y-3">
          <Skeleton variant="card" height={72} />
          <Skeleton variant="card" height={72} />
          <Skeleton variant="card" height={72} />
        </div>
      ) : items && items.length === 0 ? (
        <Card className="p-10 text-center">
          <Bell className="w-8 h-8 text-charcoal-muted mx-auto mb-3" aria-hidden="true" />
          <p className="font-semibold text-charcoal">
            {filter === "unread" ? "No unread notifications" : "Nothing here yet"}
          </p>
          <p className="text-xs text-charcoal-muted mt-1">
            Matches, likes, applications, visits and messages show up here.
          </p>
        </Card>
      ) : (
        groups.map((group) => (
          <section key={group.label} aria-label={group.label} className="space-y-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-charcoal-muted">{group.label}</h2>
            <Card className="divide-y divide-slate-100 overflow-hidden">
              {group.items.map((n) => {
                const Icon = ICONS[n.category ?? ""] ?? Bell;
                return (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => open(n)}
                    className={`w-full text-left p-4 flex items-start gap-3 hover:bg-slate-50 transition-colors ${
                      n.is_read ? "" : "bg-pale-green/15"
                    }`}
                  >
                    <span className="w-9 h-9 rounded-full bg-forest-pale text-forest flex items-center justify-center shrink-0">
                      <Icon className="w-4 h-4" aria-hidden="true" />
                    </span>
                    <span className="flex-1 min-w-0">
                      <span className="flex items-start justify-between gap-2">
                        <span className={`text-sm text-charcoal ${n.is_read ? "font-medium" : "font-bold"}`}>{n.title}</span>
                        <span className="text-[11px] text-charcoal-muted shrink-0">{timeAgo(n.created_at)}</span>
                      </span>
                      <span className="block text-xs text-charcoal-muted mt-0.5">{n.body}</span>
                      {!n.is_read && <span className="sr-only">Unread</span>}
                    </span>
                    {!n.is_read && <span aria-hidden="true" className="mt-2 w-2 h-2 rounded-full bg-forest shrink-0" />}
                  </button>
                );
              })}
            </Card>
          </section>
        ))
      )}

      {hasMore && (
        <div className="text-center">
          <Button variant="outline" onClick={loadMore} isLoading={loadingMore} className="min-h-[44px]">
            Load older
          </Button>
        </div>
      )}
    </div>
  );
}
