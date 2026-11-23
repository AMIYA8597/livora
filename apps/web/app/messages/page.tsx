"use client";

import React, { Suspense, useState, useEffect, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import {
  ConversationDTO, MessageDTO, AttachmentDTO,
  ConversationParticipantDTO
} from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useApiQuery } from "@/hooks/useApiQuery";
import { useSocket } from "@/hooks/useSocket";
import { Card, Avatar, Button } from "@flatmate/ui";
import { ChatWindow } from "@/features/messaging/components/ChatWindow";
import { PageLoading } from "@/components/states/PageLoading";
import { loginHref } from "@/lib/navigation";
import Link from "next/link";
import {
  MessageSquare, ShieldCheck, Search, Users, Home, UserCheck,
  Archive, BellOff, MoreVertical, X, AlertCircle, RefreshCw
} from "lucide-react";

type FilterTab = "all" | "direct" | "property_inquiry" | "group" | "archived";

function MessagesView() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const conversationsQuery = useApiQuery<ConversationDTO[]>(isAuthenticated ? "/messaging/conversations" : null);
  const conversationsData = conversationsQuery.data;
  const conversations = useMemo(() => conversationsData ?? [], [conversationsData]);
  const setConversations = (update: (prev: ConversationDTO[]) => ConversationDTO[]) =>
    conversationsQuery.setData((prev) => update(prev ?? []));
  const loadConversations = conversationsQuery.refetch;
  const isLoading = authLoading || conversationsQuery.isLoading;
  // Until the user picks one, open the conversation named in the URL (e.g. "Message the host"),
  // otherwise the newest one.
  const requestedConvId = useSearchParams().get("conversationId");
  const [selectedConvId, setActiveConvId] = useState<string | null>(null);
  // Phones show one pane at a time: the list, or the open chat full-screen.
  const [mobilePane, setMobilePane] = useState<"list" | "chat">(() => (requestedConvId ? "chat" : "list"));
  const activeConvId =
    selectedConvId ??
    (requestedConvId && conversations.some((c) => c.id === requestedConvId) ? requestedConvId : null) ??
    conversations[0]?.id ??
    null;
  const [messages, setMessages] = useState<MessageDTO[]>([]);
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [typingUsers, setTypingUsers] = useState<string[]>([]);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [activeConvDetails, setActiveConvDetails] = useState<any>(null);

  // Real-time WebSocket hook with full callbacks
  const { isConnected, sendEvent, startTyping, stopTyping, markRead } = useSocket({
    onMessageCreated: (newMsg: MessageDTO) => {
      if (newMsg.conversation_id === activeConvId) {
        setMessages((prev) => {
          // Deduplicate by id or idempotency_key
          const exists = prev.some(
            (m) => m.id === newMsg.id || (m.idempotency_key && m.idempotency_key === newMsg.idempotency_key)
          );
          if (exists) {
            return prev.map((m) =>
              (m.id === newMsg.id || (m.idempotency_key && m.idempotency_key === newMsg.idempotency_key))
                ? { ...newMsg, status: "sent" }
                : m
            );
          }
          return [...prev, { ...newMsg, status: "sent" }];
        });
        // Mark as read immediately if current active conversation
        markRead(activeConvId, newMsg.id);
      }

      // Update conversation in sidebar list
      setConversations((prev) =>
        prev.map((c) =>
          c.id === newMsg.conversation_id
            ? {
                ...c,
                last_message: newMsg,
                last_message_at: newMsg.sent_at,
                unread_count: c.id === activeConvId ? 0 : (c.unread_count || 0) + 1,
              }
            : c
        )
      );
    },
    onMessageUpdated: (data) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === data.id
            ? { ...m, content: data.content, is_edited: data.is_edited, edited_at: data.edited_at }
            : m
        )
      );
    },
    onMessageDeleted: (data) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === data.id
            ? { ...m, content: "This message was deleted.", is_deleted: true, deleted_at: data.deleted_at }
            : m
        )
      );
    },
    onMessageRead: (data) => {
      // If another user read messages, update status of my sent messages
      if (data.conversation_id === activeConvId && data.user_id !== user?.id) {
        setMessages((prev) =>
          prev.map((m) => (m.sender_id === user?.id ? { ...m, status: "read" } : m))
        );
      }
    },
    onTypingStarted: (data) => {
      if (data.conversation_id === activeConvId && data.user_id !== user?.id) {
        setTypingUsers((prev) => (prev.includes("Participant") ? prev : [...prev, "Participant"]));
      }
    },
    onTypingStopped: (data) => {
      if (data.conversation_id === activeConvId) {
        setTypingUsers([]);
      }
    },
  });

  // Messages & details for the active conversation. Kept in local state because the socket
  // appends to it; a late response for a conversation the user already left is dropped.
  const setConversationsData = conversationsQuery.setData;
  useEffect(() => {
    if (!activeConvId) return;
    const controller = new AbortController();
    Promise.all([
      apiClient<MessageDTO[]>(`/messaging/conversations/${activeConvId}/messages`, { signal: controller.signal }),
      apiClient<any>(`/messaging/conversations/${activeConvId}`, { signal: controller.signal }),
    ]).then(
      ([msgs, details]) => {
        if (controller.signal.aborted) return;
        setMessages(msgs);
        setActiveConvDetails(details);
        // Reset unread count in sidebar
        setConversationsData((prev = []) =>
          prev.map((c) => (c.id === activeConvId ? { ...c, unread_count: 0 } : c))
        );
      },
      (err) => {
        if (!controller.signal.aborted) console.error("Failed to load active conversation messages:", err);
      },
    );
    return () => controller.abort();
  }, [activeConvId, setConversationsData]);

  // Handle optimistic message sending
  const handleSendMessage = async (text: string, replyToId?: string, attachmentIds?: string[]) => {
    if (!activeConvId) return;

    const tempId = `temp-${Date.now()}`;
    const idempotencyKey = crypto.randomUUID ? crypto.randomUUID() : `key-${Date.now()}-${Math.random()}`;

    // Optimistic message entry
    const optimisticMsg: MessageDTO = {
      id: tempId,
      conversation_id: activeConvId,
      sender_id: user?.id || "",
      content: text,
      message_type: "text",
      idempotency_key: idempotencyKey,
      reply_to_message_id: replyToId,
      is_edited: false,
      is_deleted: false,
      is_read: false,
      sent_at: new Date().toISOString(),
      status: "sending",
    };

    setMessages((prev) => [...prev, optimisticMsg]);

    try {
      const persisted = await apiClient<MessageDTO>("/messaging/messages", {
        method: "POST",
        body: JSON.stringify({
          conversation_id: activeConvId,
          content: text,
          message_type: "text",
          idempotency_key: idempotencyKey,
          reply_to_message_id: replyToId,
          attachment_ids: attachmentIds || [],
        }),
      });

      // Reconcile optimistic entry
      setMessages((prev) =>
        prev.map((m) => (m.id === tempId ? { ...persisted, status: "sent" } : m))
      );
    } catch (err) {
      console.error("Failed to persist message:", err);
      setMessages((prev) =>
        prev.map((m) => (m.id === tempId ? { ...m, status: "failed" } : m))
      );
    }
  };

  // Handle message edit
  const handleEditMessage = async (messageId: string, newContent: string) => {
    try {
      await apiClient(`/messaging/messages/${messageId}`, {
        method: "PATCH",
        body: JSON.stringify({ content: newContent }),
      });
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, content: newContent, is_edited: true } : m))
      );
    } catch (err) {
      console.error("Failed to edit message:", err);
    }
  };

  // Handle message soft deletion
  const handleDeleteMessage = async (messageId: string) => {
    try {
      await apiClient(`/messaging/messages/${messageId}`, {
        method: "DELETE",
      });
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, content: "This message was deleted.", is_deleted: true } : m))
      );
    } catch (err) {
      console.error("Failed to delete message:", err);
    }
  };

  // Handle attachment file upload
  const handleUploadAttachment = async (file: File): Promise<AttachmentDTO> => {
    if (!activeConvId) throw new Error("No active conversation");
    const formData = new FormData();
    formData.append("file", file);
    // apiClient targets the API origin (a relative /api/v1 URL hit the Next.js server and 404'd)
    // and handles token refresh; it leaves Content-Type to the browser for FormData.
    return apiClient<AttachmentDTO>(`/messaging/conversations/${activeConvId}/attachments`, {
      method: "POST",
      body: formData,
      timeoutMs: 60000,
    });
  };

  // Filtered conversations
  const filteredConversations = useMemo(() => {
    return conversations.filter((c) => {
      // Tab filter
      if (activeTab === "archived") {
        if (!c.preferences?.is_archived) return false;
      } else {
        if (c.preferences?.is_archived) return false;
        if (activeTab !== "all" && c.type !== activeTab) return false;
      }

      // Search query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = c.title && c.title.toLowerCase().includes(q);
        const matchesMsg = c.last_message?.content?.toLowerCase().includes(q);
        if (!matchesTitle && !matchesMsg) return false;
      }
      return true;
    });
  }, [conversations, activeTab, searchQuery]);

  // Current active conversation
  const currentConv = useMemo(() => {
    return conversations.find((c) => c.id === activeConvId);
  }, [conversations, activeConvId]);

  if (authLoading) return <PageLoading text="Loading messages…" />;

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <MessageSquare className="w-12 h-12 text-forest mx-auto mb-3" />
        <h2 className="text-xl font-bold text-slate-900">Sign in to see your messages</h2>
        <Link href={loginHref("/messages")}>
          <Button variant="primary" className="mt-4 min-h-[44px]">Sign in</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto md:px-6 lg:px-8 md:py-6 h-[calc(100dvh-8rem-env(safe-area-inset-bottom))] lg:h-[calc(100dvh-7rem)] flex flex-col">
      <Card className="h-full border-0 md:border border-slate-200/80 rounded-none md:rounded-2xl flex overflow-hidden md:shadow-md">
        {/* Sidebar: Conversations List */}
        <div className={`${mobilePane === "chat" ? "hidden" : "flex"} md:flex w-full md:w-80 lg:w-96 shrink-0 border-r border-slate-200 bg-slate-50/50 flex-col`}>
          {/* Header & Status */}
          <div className="p-4 border-b border-slate-200">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-900 text-lg">Messages</h2>
              <div className="flex items-center space-x-1.5 text-xs text-slate-500">
                <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`} />
                <span>{isConnected ? "Connected" : "Connecting..."}</span>
              </div>
            </div>

            {/* Search Input */}
            <div className="relative mt-3">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search conversations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search conversations"
                className="w-full pl-9 pr-4 py-2.5 md:py-1.5 text-base md:text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {/* Filter Tabs */}
            <div className="flex items-center space-x-1 mt-3 overflow-x-auto pb-1 text-xs">
              <button
                onClick={() => setActiveTab("all")}
                className={`px-3 min-h-[44px] md:min-h-0 md:px-2.5 md:py-1 rounded-md font-medium whitespace-nowrap transition-colors ${
                  activeTab === "all" ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-200/60"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setActiveTab("direct")}
                className={`px-3 min-h-[44px] md:min-h-0 md:px-2.5 md:py-1 rounded-md font-medium whitespace-nowrap transition-colors ${
                  activeTab === "direct" ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-200/60"
                }`}
              >
                Direct
              </button>
              <button
                onClick={() => setActiveTab("property_inquiry")}
                className={`px-3 min-h-[44px] md:min-h-0 md:px-2.5 md:py-1 rounded-md font-medium whitespace-nowrap transition-colors ${
                  activeTab === "property_inquiry" ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-200/60"
                }`}
              >
                Properties
              </button>
              <button
                onClick={() => setActiveTab("group")}
                className={`px-3 min-h-[44px] md:min-h-0 md:px-2.5 md:py-1 rounded-md font-medium whitespace-nowrap transition-colors ${
                  activeTab === "group" ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-200/60"
                }`}
              >
                Groups
              </button>
              <button
                onClick={() => setActiveTab("archived")}
                className={`px-3 min-h-[44px] md:min-h-0 md:px-2.5 md:py-1 rounded-md font-medium whitespace-nowrap transition-colors ${
                  activeTab === "archived" ? "bg-forest text-white" : "text-charcoal-muted hover:bg-slate-200/60"
                }`}
              >
                Archived
              </button>
            </div>
          </div>

          {/* Conversations Scrollable List */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {isLoading ? (
              <div className="p-8 text-center text-xs text-charcoal-muted flex flex-col items-center">
                <RefreshCw className="w-5 h-5 animate-spin mb-2 text-forest" />
                <span>Loading conversations...</span>
              </div>
            ) : conversationsQuery.error ? (
              <div role="alert" className="p-8 text-center text-xs text-rose-700 flex flex-col items-center gap-2">
                <AlertCircle className="w-5 h-5" />
                <span>Couldn&apos;t load conversations.</span>
                <Button size="sm" variant="outline" onClick={loadConversations}>
                  Try again
                </Button>
              </div>
            ) : filteredConversations.length === 0 ? (
              <div className="p-8 text-center text-xs text-charcoal-muted">
                No conversations found. Explore verified flatmates or property listings to begin chatting!
              </div>
            ) : (
              filteredConversations.map((c) => {
                const isActive = c.id === activeConvId;
                const isGroup = c.type === "group";
                const isProp = c.type === "property_inquiry";
                const title = c.title || (isGroup ? "Flatmate Group" : isProp ? "Property Enquiry" : "Flatmate Seeker");
                const hasUnread = (c.unread_count || 0) > 0;

                return (
                  <button
                    key={c.id}
                    onClick={() => {
                      setActiveConvId(c.id);
                      setMobilePane("chat");
                    }}
                    className={`w-full p-3.5 text-left flex items-start space-x-3 transition-colors ${
                      isActive ? "bg-white border-l-4 border-forest shadow-2xs" : "hover:bg-slate-100/60"
                    }`}
                  >
                    <div className="relative">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-xs ${
                        isGroup ? "bg-purple-100 text-purple-700" : isProp ? "bg-forest-pale text-forest" : "bg-forest-pale text-forest"
                      }`}>
                        {isGroup ? <Users className="w-4 h-4" /> : isProp ? <Home className="w-4 h-4" /> : title.slice(0, 2).toUpperCase()}
                      </div>
                      {/* Presence badge */}
                      <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-white" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-baseline mb-0.5">
                        <span className={`font-semibold text-xs truncate ${hasUnread ? "text-charcoal font-bold" : "text-charcoal"}`}>
                          {title}
                        </span>
                        <span className="text-[10px] text-charcoal-muted">
                          {c.last_message_at ? new Date(c.last_message_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <p className={`text-xs truncate ${hasUnread ? "font-semibold text-charcoal" : "text-charcoal-muted"}`}>
                          {c.last_message ? c.last_message.content : "No messages yet"}
                        </p>
                        {hasUnread && (
                          <span className="ml-2 px-1.5 py-0.5 text-[10px] font-bold bg-forest text-white rounded-full">
                            {c.unread_count}
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Chat Area & Optional Info Drawer */}
        <div
          className={`${
            mobilePane === "chat" ? "fixed inset-0 z-50 flex" : "hidden"
          } md:static md:z-auto md:flex md:relative flex-1 min-w-0 bg-white overflow-hidden`}
        >
          {activeConvId && currentConv ? (
            <div className="flex-1 flex flex-col h-full">
              <ChatWindow
                conversationId={activeConvId}
                recipientName={currentConv.title || (currentConv.type === "group" ? "Flatmate Group" : "Flatmate Seeker / Host")}
                recipientSubtitle={
                  currentConv.type === "property_inquiry" ? "Property Inquiry" : currentConv.type === "group" ? "Group Syndicate" : "Direct Message"
                }
                isRecipientVerified={true}
                isGroup={currentConv.type === "group"}
                participantCount={Array.isArray(currentConv.participants) ? currentConv.participants.length : 2}
                messages={messages.map((m) => ({
                  id: m.id,
                  senderId: m.sender_id,
                  senderName: m.sender_id === user?.id ? "You" : "Participant",
                  content: m.content,
                  createdAt: new Date(m.sent_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                  isSelf: m.sender_id === user?.id,
                  status: m.status || (m.is_read ? "read" : "sent"),
                  isEdited: m.is_edited,
                  isDeleted: m.is_deleted,
                  replyTo: m.reply_to ? {
                    id: m.reply_to.id,
                    senderName: m.reply_to.sender_id === user?.id ? "You" : "Participant",
                    content: m.reply_to.content,
                  } : null,
                  attachments: m.attachments,
                }))}
                typingUsers={typingUsers}
                currentUserId={user?.id}
                onSendMessage={handleSendMessage}
                onEditMessage={handleEditMessage}
                onDeleteMessage={handleDeleteMessage}
                onUploadAttachment={handleUploadAttachment}
                onTyping={(isTyping) => {
                  if (isTyping) startTyping(activeConvId);
                  else stopTyping(activeConvId);
                }}
                onOpenDetails={() => setIsDetailsOpen(!isDetailsOpen)}
                onBack={() => setMobilePane("list")}
              />
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
              <MessageSquare className="w-12 h-12 text-slate-300 mb-3" />
              <p className="text-sm font-medium text-slate-600">Select a conversation to start chatting</p>
              <button
                type="button"
                onClick={() => setMobilePane("list")}
                className="md:hidden mt-4 min-h-[44px] px-4 text-sm font-semibold text-forest"
              >
                Back to conversations
              </button>
            </div>
          )}

          {/* Details / Participant Drawer */}
          {isDetailsOpen && activeConvDetails && (
            <div className="absolute inset-0 z-10 md:static md:w-72 border-l border-slate-200 bg-slate-50 md:bg-slate-50/70 p-4 flex flex-col overflow-y-auto">
              <div className="flex items-center justify-between pb-3 border-b border-slate-200">
                <h3 className="font-bold text-sm text-slate-900">Details</h3>
                <button
                  type="button"
                  onClick={() => setIsDetailsOpen(false)}
                  aria-label="Close details"
                  className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] -mr-2 text-slate-400 hover:text-slate-700"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Context Summary */}
              <div className="py-4 border-b border-slate-200">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Type</span>
                <p className="text-xs font-semibold text-slate-800 capitalize mt-0.5">{activeConvDetails.type?.replace("_", " ")}</p>
                {activeConvDetails.title && (
                  <>
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mt-3 block">Title</span>
                    <p className="text-xs text-slate-700 mt-0.5">{activeConvDetails.title}</p>
                  </>
                )}
              </div>

              {/* Participants */}
              <div className="py-4 flex-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2 block">
                  Participants ({activeConvDetails.participant_details?.length || 0})
                </span>
                <div className="space-y-2">
                  {activeConvDetails.participant_details?.map((p: any) => (
                    <div key={p.id} className="flex items-center justify-between bg-white p-2 rounded-lg border border-slate-200">
                      <div className="flex items-center space-x-2 truncate">
                        <Avatar alt={p.user?.full_name || "User"} size="sm" />
                        <span className="text-xs font-medium text-slate-800 truncate">
                          {p.user_id === user?.id ? "You" : (p.user?.full_name || "Participant")}
                        </span>
                      </div>
                      <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 bg-slate-100 rounded text-slate-600">
                        {p.role}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Preferences / Actions */}
              <div className="pt-4 border-t border-slate-200 space-y-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start text-xs text-slate-700"
                  onClick={async () => {
                    await apiClient(`/messaging/conversations/${activeConvId}/preferences`, {
                      method: "PATCH",
                      body: JSON.stringify({ is_archived: !activeConvDetails.preferences?.is_archived }),
                    });
                    loadConversations();
                  }}
                >
                  <Archive className="w-3.5 h-3.5 mr-2" />
                  {activeConvDetails.preferences?.is_archived ? "Unarchive Conversation" : "Archive Conversation"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

export default function MessagesPage() {
  // useSearchParams needs a Suspense boundary so the rest of the route can prerender.
  return (
    <Suspense fallback={<PageLoading text="Loading messages…" />}>
      <MessagesView />
    </Suspense>
  );
}
