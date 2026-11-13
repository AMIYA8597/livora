"use client";

import React, { useState, useEffect } from "react";
import { ConversationDTO, MessageDTO } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useSocket } from "@/hooks/useSocket";
import { Card, Avatar, Input, Button } from "@flatmate/ui";
import { Send, MessageSquare, Check, CheckCheck } from "lucide-react";

export default function MessagesPage() {
  const { user, isAuthenticated } = useAuth();
  const [conversations, setConversations] = useState<ConversationDTO[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageDTO[]>([]);
  const [inputContent, setInputContent] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  // Realtime WebSocket integration
  const { isConnected, sendEvent } = useSocket((newMsg: MessageDTO) => {
    if (newMsg.conversation_id === activeConvId) {
      setMessages((prev) => [...prev, newMsg]);
    }
    // Update last message in thread list
    setConversations((prev) =>
      prev.map((c) =>
        c.id === newMsg.conversation_id ? { ...c, last_message: newMsg, last_message_at: newMsg.sent_at } : c
      )
    );
  });

  // 1. Fetch conversations
  useEffect(() => {
    async function loadConversations() {
      if (!isAuthenticated) return;
      try {
        setIsLoading(true);
        const data = await apiClient<ConversationDTO[]>("/messaging/conversations");
        setConversations(data);
        if (data.length > 0 && !activeConvId) {
          setActiveConvId(data[0].id);
        }
      } catch (err) {
        console.error("Failed to load conversations:", err);
      } finally {
        setIsLoading(false);
      }
    }
    loadConversations();
  }, [isAuthenticated, activeConvId]);

  // 2. Fetch messages for active conversation
  useEffect(() => {
    async function loadMessages() {
      if (!activeConvId) return;
      try {
        const data = await apiClient<MessageDTO[]>(`/messaging/conversations/${activeConvId}/messages`);
        setMessages(data);
      } catch (err) {
        console.error("Failed to load messages:", err);
      }
    }
    loadMessages();
  }, [activeConvId]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputContent.trim() || !activeConvId) return;

    const text = inputContent.trim();
    setInputContent("");

    try {
      const newMsg = await apiClient<MessageDTO>("/messaging/messages", {
        method: "POST",
        body: JSON.stringify({
          conversation_id: activeConvId,
          content: text,
          message_type: "text",
        }),
      });
      setMessages((prev) => [...prev, newMsg]);
    } catch (err: any) {
      console.error("Send message error:", err);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <MessageSquare className="w-12 h-12 text-indigo-600 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-slate-900">Please sign in to access your messages</h2>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 h-[calc(100vh-140px)]">
      <Card className="h-full border-slate-200/80 flex overflow-hidden shadow-md">
        {/* Conversations Sidebar */}
        <div className="w-80 border-r border-slate-200/80 bg-slate-50/50 flex flex-col">
          <div className="p-4 border-b border-slate-200/80">
            <h2 className="font-bold text-slate-900 text-lg">Direct Messages</h2>
            <div className="flex items-center space-x-1.5 mt-1 text-xs text-slate-500">
              <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-500" : "bg-amber-500"}`} />
              <span>{isConnected ? "Realtime connected" : "Connecting..."}</span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {conversations.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                No active conversations yet. Visit a listing or flatmate to start chatting.
              </div>
            ) : (
              conversations.map((c) => {
                const isActive = c.id === activeConvId;
                return (
                  <button
                    key={c.id}
                    onClick={() => setActiveConvId(c.id)}
                    className={`w-full p-4 text-left flex items-start space-x-3 transition-colors ${
                      isActive ? "bg-white border-l-4 border-indigo-600 shadow-2xs" : "hover:bg-slate-100/60"
                    }`}
                  >
                    <Avatar alt="Participant" size="md" />
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-baseline mb-0.5">
                        <span className="font-semibold text-xs text-slate-900 truncate">
                          {c.type === "direct" ? "Flatmate Seeker" : "Group Channel"}
                        </span>
                        <span className="text-[10px] text-slate-400">
                          {c.last_message_at ? new Date(c.last_message_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 truncate">
                        {c.last_message ? c.last_message.content : "Start a conversation..."}
                      </p>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Active Conversation Chat Window */}
        <div className="flex-1 flex flex-col bg-white">
          {activeConvId ? (
            <>
              {/* Chat Header */}
              <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <Avatar alt="Active Chat" size="sm" isVerified={true} />
                  <div>
                    <h3 className="font-bold text-slate-900 text-sm">Active Conversation</h3>
                    <span className="text-[11px] text-emerald-600 font-medium">Online</span>
                  </div>
                </div>
              </div>

              {/* Messages Stream */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-xs text-slate-400">
                    Say hello and introduce yourself!
                  </div>
                ) : (
                  messages.map((m) => {
                    const isMe = m.sender_id === user?.id;
                    return (
                      <div
                        key={m.id}
                        className={`flex flex-col ${isMe ? "items-end" : "items-start"}`}
                      >
                        <div
                          className={`max-w-md px-4 py-2.5 rounded-2xl text-xs leading-relaxed shadow-2xs ${
                            isMe
                              ? "bg-indigo-600 text-white rounded-br-none"
                              : "bg-slate-100 text-slate-800 rounded-bl-none"
                          }`}
                        >
                          {m.content}
                        </div>
                        <span className="text-[10px] text-slate-400 mt-1 px-1 flex items-center space-x-1">
                          <span>{new Date(m.sent_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                          {isMe && <CheckCheck className="w-3 h-3 text-indigo-500" />}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Chat Input Bar */}
              <form onSubmit={handleSendMessage} className="p-3 border-t border-slate-100 flex items-center gap-2">
                <input
                  type="text"
                  value={inputContent}
                  onChange={(e) => setInputContent(e.target.value)}
                  placeholder="Type a message..."
                  className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white"
                />
                <Button type="submit" variant="primary" size="sm" className="px-4 py-2.5">
                  <Send className="w-4 h-4" />
                </Button>
              </form>
            </>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-400 text-xs">
              Select a conversation to start chatting.
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
