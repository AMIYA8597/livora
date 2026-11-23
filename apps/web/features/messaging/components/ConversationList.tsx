"use client";

import React, { useMemo, useState } from "react";
import type { ConversationDTO } from "@flatmate/contracts";
import { Button } from "@flatmate/ui";
import { AlertCircle, BellOff, Home, RefreshCw, Search, Users } from "lucide-react";
import { conversationTitle, otherParticipants, type Presence } from "../chat-model";
import type { SocketStatus } from "@/hooks/useSocket";

type FilterTab = "all" | "direct" | "property_inquiry" | "group" | "archived";

const TABS: { id: FilterTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "direct", label: "Direct" },
  { id: "property_inquiry", label: "Properties" },
  { id: "group", label: "Groups" },
  { id: "archived", label: "Archived" },
];

const STATUS_TEXT: Record<SocketStatus, string> = {
  idle: "Not connected",
  connecting: "Connecting…",
  open: "Live",
  offline: "Offline: messages will send when you're back",
};

interface ConversationListProps {
  conversations: ConversationDTO[];
  activeId: string | null;
  myId?: string;
  presence: Record<string, Presence>;
  socketStatus: SocketStatus;
  isLoading: boolean;
  error: Error | null;
  onRetry: () => void;
  onSelect: (id: string) => void;
}

function timeLabel(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date();
  return d.toDateString() === today.toDateString()
    ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString([], { day: "numeric", month: "short" });
}

export function ConversationList({
  conversations, activeId, myId, presence, socketStatus, isLoading, error, onRetry, onSelect,
}: ConversationListProps) {
  const [tab, setTab] = useState<FilterTab>("all");
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return conversations.filter((c) => {
      const archived = Boolean(c.preferences?.is_archived);
      if (tab === "archived" ? !archived : archived) return false;
      if (tab !== "all" && tab !== "archived" && c.type !== tab) return false;
      if (!q) return true;
      return (
        conversationTitle(c, myId).toLowerCase().includes(q) ||
        Boolean(c.title?.toLowerCase().includes(q)) ||
        Boolean(!c.last_message?.is_deleted && c.last_message?.content?.toLowerCase().includes(q))
      );
    });
  }, [conversations, tab, query, myId]);

  return (
    <>
      <div className="p-4 border-b border-slate-200">
        <div className="flex items-center justify-between gap-2">
          <h1 className="font-bold text-slate-900 text-lg">Messages</h1>
          <div className="flex items-center gap-1.5 text-xs text-slate-500 min-w-0" role="status">
            <span
              className={`w-2 h-2 shrink-0 rounded-full ${
                socketStatus === "open" ? "bg-emerald-500" : socketStatus === "offline" ? "bg-rose-500" : "bg-amber-500"
              }`}
              aria-hidden="true"
            />
            <span className="truncate">{STATUS_TEXT[socketStatus]}</span>
          </div>
        </div>

        <div className="relative mt-3">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
          <input
            type="search"
            placeholder="Search people and messages"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search conversations"
            className="w-full pl-9 pr-4 py-2.5 md:py-1.5 text-base md:text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center gap-1 mt-3 overflow-x-auto pb-1 text-xs" role="tablist" aria-label="Filter conversations">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              className={`px-3 min-h-[44px] md:min-h-0 md:px-2.5 md:py-1 rounded-md font-medium whitespace-nowrap transition-colors ${
                tab === t.id ? "bg-forest text-white" : "text-slate-600 hover:bg-slate-200/60"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
        {isLoading ? (
          <div className="p-8 text-center text-xs text-charcoal-muted flex flex-col items-center" aria-busy="true">
            <RefreshCw className="w-5 h-5 animate-spin mb-2 text-forest" aria-hidden="true" />
            <span>Loading conversations…</span>
          </div>
        ) : error ? (
          <div role="alert" className="p-8 text-center text-xs text-rose-700 flex flex-col items-center gap-2">
            <AlertCircle className="w-5 h-5" aria-hidden="true" />
            <span>Couldn&apos;t load conversations. {error.message}</span>
            <Button size="sm" variant="outline" onClick={onRetry}>Try again</Button>
          </div>
        ) : visible.length === 0 ? (
          <div className="p-8 text-center text-xs text-charcoal-muted">
            {conversations.length === 0
              ? "No conversations yet. Message a host from a listing, or say hello to a match."
              : "No conversations match."}
          </div>
        ) : (
          visible.map((c) => {
            const title = conversationTitle(c, myId);
            const isGroup = c.type === "group";
            const isProp = c.type === "property_inquiry";
            const unread = c.unread_count ?? 0;
            const muted = Boolean(c.preferences?.is_muted);
            const other = !isGroup ? otherParticipants(c, myId)[0] : undefined;
            const online = other ? presence[other.user_id]?.status === "online" : false;
            const preview = c.last_message
              ? `${c.last_message.sender_id === myId ? "You: " : ""}${
                  c.last_message.is_deleted
                    ? "Message deleted"
                    : c.last_message.content || (c.last_message.attachments?.length ? "Sent an attachment" : "")
                }`
              : "No messages yet";

            return (
              <button
                key={c.id}
                type="button"
                onClick={() => onSelect(c.id)}
                aria-current={c.id === activeId ? "true" : undefined}
                className={`w-full p-3.5 text-left flex items-start gap-3 transition-colors ${
                  c.id === activeId ? "bg-white border-l-4 border-forest shadow-2xs" : "hover:bg-slate-100/60"
                }`}
              >
                <div className="relative shrink-0">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-xs ${
                      isGroup ? "bg-purple-100 text-purple-700" : "bg-forest-pale text-forest"
                    }`}
                    aria-hidden="true"
                  >
                    {isGroup ? <Users className="w-4 h-4" /> : isProp && !other ? <Home className="w-4 h-4" /> : title.slice(0, 2).toUpperCase()}
                  </div>
                  {online && (
                    <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-white">
                      <span className="sr-only">Online</span>
                    </span>
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-baseline gap-2 mb-0.5">
                    <span className={`text-xs truncate text-charcoal ${unread ? "font-bold" : "font-semibold"}`}>{title}</span>
                    <span className="text-[10px] text-charcoal-muted shrink-0">{timeLabel(c.last_message_at)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <p className={`text-xs truncate ${unread ? "font-semibold text-charcoal" : "text-charcoal-muted"}`}>{preview}</p>
                    <span className="flex items-center gap-1 shrink-0">
                      {muted && <BellOff className="w-3 h-3 text-slate-400" aria-label="Muted" />}
                      {unread > 0 && (
                        <span className="px-1.5 py-0.5 text-[10px] font-bold bg-forest text-white rounded-full">
                          {unread}
                          <span className="sr-only"> unread</span>
                        </span>
                      )}
                    </span>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </>
  );
}
