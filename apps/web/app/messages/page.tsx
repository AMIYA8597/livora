"use client";

import React, { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button, Card } from "@flatmate/ui";
import type { ConversationDTO } from "@flatmate/contracts";
import { MessageSquare } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useApiQuery } from "@/hooks/useApiQuery";
import { loginHref } from "@/lib/navigation";
import { PageLoading } from "@/components/states/PageLoading";
import { InlineNotice } from "@/components/states/InlineNotice";
import { ChatWindow, type MessageItem } from "@/features/messaging/components/ChatWindow";
import { ConversationList } from "@/features/messaging/components/ConversationList";
import { ConversationDetails } from "@/features/messaging/components/ConversationDetails";
import { useChat } from "@/features/messaging/useChat";
import {
  conversationSubtitle,
  conversationTitle,
  deliveryStatus,
  otherParticipants,
  presenceLabel,
  safetyWarning,
  senderName,
} from "@/features/messaging/chat-model";

function MessagesView() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const myId = user?.id;

  // Until the user picks one, open the conversation named in the URL (e.g. "Message the host"),
  // otherwise the newest one.
  const requestedConvId = useSearchParams().get("conversationId");
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  // Phones show one pane at a time: the list, or the open chat full-screen.
  const [mobilePane, setMobilePane] = useState<"list" | "chat">(() => (requestedConvId ? "chat" : "list"));
  const [detailsOpen, setDetailsOpen] = useState(false);

  const inbox = useApiQuery<ConversationDTO[]>(isAuthenticated ? "/messaging/conversations" : null);
  const conversations = useMemo(() => inbox.data ?? [], [inbox.data]);
  const activeConvId =
    selectedConvId ??
    (requestedConvId && conversations.some((c) => c.id === requestedConvId) ? requestedConvId : null) ??
    conversations[0]?.id ??
    null;

  const chat = useChat(isAuthenticated ? myId : undefined, activeConvId, inbox);

  const summary = conversations.find((c) => c.id === activeConvId);
  const details = chat.active.details ?? summary;

  const items: MessageItem[] = useMemo(
    () =>
      chat.active.messages.map((m) => ({
        id: m.id,
        senderId: m.sender_id,
        senderName: senderName(details, m.sender_id, myId),
        content: m.content,
        createdAt: new Date(m.sent_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        isSelf: m.sender_id === myId,
        status: m.sender_id === myId ? deliveryStatus(m, chat.active.cursors) : undefined,
        isEdited: m.is_edited,
        isDeleted: m.is_deleted,
        replyTo: m.reply_to
          ? { id: m.reply_to.id, senderName: senderName(details, m.reply_to.sender_id, myId), content: m.reply_to.content }
          : null,
        attachments: m.attachments,
        // Warnings protect the recipient; the sender isn't shown one about their own message.
        safetyWarning: m.sender_id !== myId && !m.is_deleted ? safetyWarning(m) : null,
        contactHidden: m.contact_hidden,
        isSystem: m.message_type === "system",
      })),
    [chat.active.messages, chat.active.cursors, details, myId],
  );

  if (authLoading) return <PageLoading text="Loading messages…" />;

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <MessageSquare className="w-12 h-12 text-forest mx-auto mb-3" />
        <h1 className="text-xl font-bold text-slate-900">Sign in to see your messages</h1>
        <Link href={loginHref("/messages")}>
          <Button variant="primary" className="mt-4 min-h-[44px]">Sign in</Button>
        </Link>
      </div>
    );
  }

  const isGroup = details?.type === "group";
  const other = details && !isGroup ? otherParticipants(details, myId)[0] : undefined;
  const subtitle = details
    ? (other && presenceLabel(chat.presence[other.user_id])) || conversationSubtitle(details, myId)
    : "";
  const typingNames = chat.typingIds.map((id) => senderName(details, id, myId));

  return (
    <div className="max-w-7xl mx-auto md:px-6 lg:px-8 md:py-6 h-[calc(100dvh-8rem-env(safe-area-inset-bottom))] lg:h-[calc(100dvh-7rem)] flex flex-col">
      <Card className="h-full border-0 md:border border-slate-200/80 rounded-none md:rounded-2xl flex overflow-hidden md:shadow-md">
        <div className={`${mobilePane === "chat" ? "hidden" : "flex"} md:flex w-full md:w-80 lg:w-96 shrink-0 border-r border-slate-200 bg-slate-50/50 flex-col`}>
          <ConversationList
            conversations={conversations}
            activeId={activeConvId}
            myId={myId}
            presence={chat.presence}
            socketStatus={chat.socketStatus}
            isLoading={inbox.isLoading}
            error={inbox.error}
            onRetry={inbox.refetch}
            onSelect={(id) => {
              setSelectedConvId(id);
              setMobilePane("chat");
            }}
          />
        </div>

        <div
          className={`${mobilePane === "chat" ? "fixed inset-0 z-50 flex" : "hidden"} md:static md:z-auto md:flex md:relative flex-1 min-w-0 bg-white overflow-hidden`}
        >
          {activeConvId && details ? (
            <div className="flex-1 flex flex-col h-full min-w-0">
              {chat.active.error && (
                <div className="px-3 pt-3">
                  <InlineNotice tone="error">{chat.active.error}</InlineNotice>
                </div>
              )}
              <ChatWindow
                conversationId={activeConvId}
                recipientName={conversationTitle(details, myId)}
                recipientSubtitle={subtitle}
                isRecipientVerified={Boolean(other?.user?.is_verified)}
                contactsLocked={Boolean(details.contacts_locked)}
                isGroup={isGroup}
                participantCount={details.participant_details?.length ?? 2}
                messages={items}
                typingUsers={typingNames}
                currentUserId={myId}
                onSendMessage={chat.send}
                onRetry={chat.retry}
                onEditMessage={chat.edit}
                onDeleteMessage={chat.remove}
                onUploadAttachment={chat.upload}
                onTyping={chat.setMyTyping}
                onRequestSuggestions={chat.suggest}
                onOpenDetails={() => setDetailsOpen((o) => !o)}
                onBack={() => setMobilePane("list")}
              />
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
              <MessageSquare className="w-12 h-12 text-slate-300 mb-3" />
              <p className="text-sm font-medium text-slate-600">
                {conversations.length ? "Pick a conversation" : "Your conversations will appear here"}
              </p>
              <button
                type="button"
                onClick={() => setMobilePane("list")}
                className="md:hidden mt-4 min-h-[44px] px-4 text-sm font-semibold text-forest"
              >
                Back to conversations
              </button>
            </div>
          )}

          {detailsOpen && chat.active.details && (
            <ConversationDetails
              key={chat.active.details.id}
              details={chat.active.details}
              myId={myId}
              onClose={() => setDetailsOpen(false)}
              onChanged={inbox.refetch}
            />
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
