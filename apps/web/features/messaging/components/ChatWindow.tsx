"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Send, ShieldAlert, Check, CheckCheck, Paperclip, X,
  CornerUpLeft, MoreVertical, Edit2, Trash2, FileText, Download,
  Users, Info, ShieldCheck, Clock, ArrowLeft
} from "lucide-react";
import { AttachmentDTO } from "@flatmate/contracts";

export interface MessageItem {
  id: string;
  senderId: string;
  senderName: string;
  content: string;
  createdAt: string;
  isSelf: boolean;
  status?: "sending" | "sent" | "delivered" | "read" | "failed";
  isEdited?: boolean;
  isDeleted?: boolean;
  replyTo?: {
    id: string;
    senderName?: string;
    content: string;
  } | null;
  attachments?: AttachmentDTO[];
}

export interface ChatWindowProps {
  conversationId: string;
  recipientName: string;
  recipientSubtitle?: string;
  isRecipientVerified?: boolean;
  isGroup?: boolean;
  participantCount?: number;
  messages: MessageItem[];
  typingUsers?: string[];
  currentUserId?: string;
  onSendMessage: (text: string, replyToId?: string, attachmentIds?: string[]) => Promise<void>;
  onEditMessage?: (messageId: string, newContent: string) => Promise<void>;
  onDeleteMessage?: (messageId: string) => Promise<void>;
  onUploadAttachment?: (file: File) => Promise<AttachmentDTO>;
  onTyping?: (isTyping: boolean) => void;
  onOpenDetails?: () => void;
  /** Mobile only: return to the conversation list. */
  onBack?: () => void;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
  conversationId,
  recipientName,
  recipientSubtitle = "Direct Message",
  isRecipientVerified = false,
  isGroup = false,
  participantCount = 2,
  messages,
  typingUsers = [],
  currentUserId,
  onSendMessage,
  onEditMessage,
  onDeleteMessage,
  onUploadAttachment,
  onTyping,
  onOpenDetails,
  onBack,
}) => {
  const [inputText, setInputText] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [replyingTo, setReplyingTo] = useState<MessageItem | null>(null);
  // Touch screens have no hover, so tapping a message shows its actions.
  const [actionsFor, setActionsFor] = useState<string | null>(null);
  const [editingMessage, setEditingMessage] = useState<MessageItem | null>(null);
  const [stagedAttachments, setStagedAttachments] = useState<AttachmentDTO[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [activeMenuMsgId, setActiveMenuMsgId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typingUsers]);

  // Handle typing debounce
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputText(val);

    if (onTyping) {
      onTyping(true);
      if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
      typingTimeoutRef.current = setTimeout(() => {
        onTyping(false);
      }, 3000);
    }
  };

  // Pre-flight safety heuristic check & submit
  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = inputText.trim();
    if (!text && stagedAttachments.length === 0) return;

    // Rental advance scam warning check
    const isAdvanceScam = /advance\s+(money|token|rent|payment)\s+before\s+visit/i.test(text);
    const hasPhone = /(\+91[\-\s]?)?[6-9]\d{9}/.test(text);

    if (isAdvanceScam) {
      setWarning("Security Warning: Requesting or offering advance payments before physical property visits is prohibited for your protection.");
      return;
    }

    if (hasPhone && !isRecipientVerified) {
      setWarning("Notice: Sharing phone numbers prior to mutual identity verification is monitored in accordance with safety guidelines.");
    } else {
      setWarning(null);
    }

    if (editingMessage && onEditMessage) {
      await onEditMessage(editingMessage.id, text);
      setEditingMessage(null);
      setInputText("");
      return;
    }

    const attIds = stagedAttachments.map((a) => a.id);
    await onSendMessage(text, replyingTo?.id, attIds);

    setInputText("");
    setReplyingTo(null);
    setStagedAttachments([]);
    if (onTyping) onTyping(false);
  };

  // File upload trigger
  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !onUploadAttachment) return;

    try {
      setIsUploading(true);
      const att = await onUploadAttachment(file);
      setStagedAttachments((prev) => [...prev, att]);
    } catch (err: any) {
      alert(err.message || "Failed to upload attachment");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="flex flex-col h-full bg-white md:rounded-xl md:border border-slate-200 md:shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 px-2 sm:px-6 py-2 sm:py-3.5 pt-[max(0.5rem,env(safe-area-inset-top))] md:pt-3.5 border-b border-slate-200 bg-slate-50/80">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="md:hidden inline-flex items-center justify-center min-w-[44px] min-h-[44px] text-slate-600 hover:bg-slate-200/50 rounded-lg"
              aria-label="Back to conversations"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
          )}
          <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm ${
            isGroup ? "bg-purple-100 text-purple-700" : "bg-indigo-100 text-indigo-700"
          }`}>
            {isGroup ? <Users className="w-5 h-5" /> : recipientName.slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="flex items-center space-x-1.5">
              <span className="font-semibold text-slate-900 text-sm truncate">{recipientName}</span>
              {isRecipientVerified && (
                <span title="Identity Verified">
                  <ShieldCheck className="w-4 h-4 text-emerald-600 inline" />
                </span>
              )}
            </div>
            <div className="flex items-center space-x-2 text-[11px] text-slate-500">
              <span className="truncate">{isGroup ? `${participantCount} members` : recipientSubtitle}</span>
            </div>
          </div>
        </div>

        {onOpenDetails && (
          <button
            type="button"
            onClick={onOpenDetails}
            aria-label="Conversation details"
            className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] shrink-0 text-slate-500 hover:text-slate-800 hover:bg-slate-200/50 rounded-lg transition-colors"
            title="Conversation Details"
          >
            <Info className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Persistent Safety Reminder */}
      <div className="bg-warm/60 border-b border-slate-200/80 px-4 py-1.5 flex items-center justify-between text-[11px] text-charcoal-muted">
        <div className="flex items-center space-x-1.5">
          <ShieldAlert className="w-3.5 h-3.5 text-forest flex-shrink-0" />
          <span>Safety Tip: Never transfer advance deposit or token money before a physical visit. Keep all communications here.</span>
        </div>
      </div>

      {/* Dynamic Safety Warning Banner */}
      {warning && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center justify-between text-xs text-amber-800">
          <div className="flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span>{warning}</span>
          </div>
          <button onClick={() => setWarning(null)} className="text-amber-700 hover:text-amber-900">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Message Stream */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-slate-50/30">
        {messages.map((msg) => {
          const isDeleted = msg.isDeleted;
          return (
            <div
              key={msg.id}
              className={`flex flex-col group relative ${msg.isSelf ? "items-end" : "items-start"}`}
            >
              {/* Sender Name in Group Conversations */}
              {isGroup && !msg.isSelf && (
                <span className="text-[11px] font-medium text-slate-500 ml-1 mb-1">
                  {msg.senderName}
                </span>
              )}

              {/* Reply Preview Bubble inside message */}
              {msg.replyTo && (
                <div
                  className={`text-xs px-3 py-1.5 mb-1 rounded-t-lg border-l-2 max-w-[75%] truncate ${
                    msg.isSelf
                      ? "bg-indigo-100 text-indigo-900 border-indigo-500"
                      : "bg-slate-200 text-slate-700 border-slate-400"
                  }`}
                >
                  <span className="font-semibold">{msg.replyTo.senderName || "Reply"}: </span>
                  <span className="italic">{msg.replyTo.content}</span>
                </div>
              )}

              {/* Main Message Bubble */}
              <div
                onClick={() => !isDeleted && setActionsFor((cur) => (cur === msg.id ? null : msg.id))}
                className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm shadow-2xs relative break-words ${
                  msg.isSelf
                    ? "bg-indigo-600 text-white rounded-tr-none"
                    : "bg-white text-slate-900 border border-slate-200/80 rounded-tl-none"
                } ${isDeleted ? "italic text-slate-400 bg-slate-100" : ""}`}
              >
                {msg.content}

                {/* Attachments rendering */}
                {msg.attachments && msg.attachments.length > 0 && (
                  <div className="mt-2 space-y-1.5">
                    {msg.attachments.map((att) => {
                      const isImg = att.mime_type.startsWith("image/");
                      return isImg ? (
                        <div key={att.id} className="rounded-lg overflow-hidden border border-white/20 max-w-xs">
                          {att.signed_url ? (
                            <img src={att.signed_url} alt={att.file_name} className="max-h-48 w-auto object-cover" />
                          ) : (
                            <div className="p-3 bg-black/10 text-xs flex items-center space-x-2">
                              <FileText className="w-4 h-4" />
                              <span className="truncate">{att.file_name}</span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <a
                          key={att.id}
                          href={att.signed_url || "#"}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center space-x-2 p-2 rounded-lg bg-black/10 hover:bg-black/20 text-xs font-medium transition-colors"
                        >
                          <FileText className="w-4 h-4 flex-shrink-0" />
                          <span className="truncate flex-1">{att.file_name}</span>
                          <Download className="w-3.5 h-3.5 flex-shrink-0" />
                        </a>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Message Footer: Timestamp, Edit label, Receipts */}
              <div className="flex items-center space-x-1.5 mt-1 px-1 text-[10px] text-slate-400">
                <span>{msg.createdAt}</span>
                {msg.isEdited && <span className="italic">(edited)</span>}
                {msg.isSelf && !isDeleted && (
                  <span>
                    {msg.status === "sending" && <Clock className="w-3 h-3 text-slate-400" />}
                    {msg.status === "sent" && <Check className="w-3 h-3 text-slate-400" />}
                    {msg.status === "delivered" && <CheckCheck className="w-3 h-3 text-slate-400" />}
                    {msg.status === "read" && <CheckCheck className="w-3 h-3 text-indigo-500 font-bold" />}
                  </span>
                )}
              </div>

              {/* Message actions: on hover/focus with a mouse, inline under the bubble after a tap */}
              {!isDeleted && (
                <div
                  className={`items-center gap-1 bg-white border border-slate-200 rounded-lg shadow-sm px-1 py-0.5 z-10 ${
                    actionsFor === msg.id
                      ? "flex mt-1"
                      : `hidden md:flex absolute top-0 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity ${
                          msg.isSelf ? "right-[80%]" : "left-[80%]"
                        }`
                  }`}
                >
                  <button
                    aria-label="Reply"
                    onClick={() => {
                      setReplyingTo(msg);
                      setActionsFor(null);
                    }}
                    className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] md:min-w-0 md:min-h-0 md:p-1 text-slate-500 hover:text-indigo-600 rounded"
                    title="Reply"
                  >
                    <CornerUpLeft className="w-3.5 h-3.5" />
                  </button>
                  {msg.isSelf && onEditMessage && (
                    <button
                      onClick={() => {
                        setEditingMessage(msg);
                        setInputText(msg.content);
                        setActionsFor(null);
                      }}
                      aria-label="Edit"
                      className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] md:min-w-0 md:min-h-0 md:p-1 text-slate-500 hover:text-indigo-600 rounded"
                      title="Edit"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {msg.isSelf && onDeleteMessage && (
                    <button
                      onClick={() => {
                        setActionsFor(null);
                        onDeleteMessage(msg.id);
                      }}
                      aria-label="Delete"
                      className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] md:min-w-0 md:min-h-0 md:p-1 text-slate-500 hover:text-rose-600 rounded"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {/* Real-Time Typing Indicator */}
        {typingUsers.length > 0 && (
          <div className="flex items-center space-x-2 text-xs text-slate-500 italic py-1">
            <div className="flex space-x-1">
              <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce" />
              <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:0.2s]" />
              <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:0.4s]" />
            </div>
            <span>{typingUsers.join(", ")} {typingUsers.length === 1 ? "is" : "are"} typing...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Replying Banner */}
      {replyingTo && (
        <div className="bg-indigo-50 border-t border-indigo-200 px-4 py-2 flex items-center justify-between text-xs text-indigo-900">
          <div className="flex items-center space-x-2 truncate">
            <CornerUpLeft className="w-3.5 h-3.5 text-indigo-600 flex-shrink-0" />
            <span>Replying to <strong>{replyingTo.senderName}</strong>: {replyingTo.content}</span>
          </div>
          <button onClick={() => setReplyingTo(null)} className="text-indigo-600 hover:text-indigo-900 ml-2">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Editing Banner */}
      {editingMessage && (
        <div className="bg-amber-50 border-t border-amber-200 px-4 py-2 flex items-center justify-between text-xs text-amber-900">
          <span>Editing message</span>
          <button
            onClick={() => {
              setEditingMessage(null);
              setInputText("");
            }}
            className="text-amber-700 hover:text-amber-900"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Staged Attachments Preview */}
      {stagedAttachments.length > 0 && (
        <div className="bg-slate-50 px-4 py-2 border-t border-slate-200 flex flex-wrap gap-2">
          {stagedAttachments.map((att) => (
            <div
              key={att.id}
              className="flex items-center space-x-1.5 bg-white border border-slate-200 rounded-md px-2.5 py-1 text-xs text-slate-700 shadow-2xs"
            >
              <FileText className="w-3.5 h-3.5 text-indigo-600" />
              <span className="max-w-[120px] truncate">{att.file_name}</span>
              <button
                type="button"
                onClick={() => setStagedAttachments((prev) => prev.filter((a) => a.id !== att.id))}
                className="text-slate-400 hover:text-rose-600"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Composer Input Bar */}
      <form onSubmit={handleSend} className="p-2 sm:p-3 pb-[max(0.5rem,env(safe-area-inset-bottom))] border-t border-slate-200 bg-white flex items-center gap-2">
        {onUploadAttachment && (
          <>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelected}
              accept="image/jpeg,image/png,image/webp,application/pdf"
              className="hidden"
            />
            <button
              type="button"
              disabled={isUploading}
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] shrink-0 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
              title="Attach a photo or PDF (max 10 MB)"
              aria-label="Attach a photo or PDF"
            >
              <Paperclip className="w-4 h-4" />
            </button>
          </>
        )}

        <input
          type="text"
          value={inputText}
          onChange={handleInputChange}
          placeholder="Type a message…"
          aria-label="Message"
          className="flex-1 min-w-0 min-h-[44px] border border-slate-300 rounded-lg px-3 sm:px-4 py-2 text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
        />

        <button
          type="submit"
          disabled={!inputText.trim() && stagedAttachments.length === 0}
          className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] shrink-0 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors disabled:opacity-50"
          title="Send"
          aria-label="Send"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
};
