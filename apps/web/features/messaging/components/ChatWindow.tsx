"use client";

import React, { useState } from 'react';
import { Send, ShieldAlert, CheckCircle2 } from 'lucide-react';

export interface MessageItem {
  id: string;
  senderId: string;
  senderName: string;
  content: string;
  createdAt: string;
  isSelf: boolean;
}

export interface ChatWindowProps {
  conversationId: string;
  recipientName: string;
  isRecipientVerified: boolean;
  messages: MessageItem[];
  onSendMessage: (text: string) => Promise<void>;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
  recipientName,
  isRecipientVerified,
  messages,
  onSendMessage,
}) => {
  const [inputText, setInputText] = useState('');
  const [warning, setWarning] = useState<string | null>(null);

  // Local safety heuristic check before dispatch
  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = inputText.trim();
    if (!text) return;

    // Rental advance scam warning check
    const isAdvanceScam = /advance\s+(money|token|rent|payment)\s+before\s+visit/i.test(text);
    const hasPhone = /(\+91[\-\s]?)?[6-9]\d{9}/.test(text);

    if (isAdvanceScam) {
      setWarning('Warning: Requesting or offering advance payments before physical property visits is prohibited for your protection.');
      return;
    }

    if (hasPhone && !isRecipientVerified) {
      setWarning('Notice: Sharing personal contact numbers before mutual match confirmation is masked in accordance with data privacy guidelines.');
    } else {
      setWarning(null);
    }

    await onSendMessage(text);
    setInputText('');
  };

  return (
    <div className="flex flex-col h-[600px] bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Chat Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50/50">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-sm">
            {recipientName.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-semibold text-gray-900 text-sm">{recipientName}</span>
              {isRecipientVerified && (
                <span title="Verified Identity">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 inline" />
                </span>
              )}
            </div>
            <span className="text-[11px] text-gray-400">
              {isRecipientVerified ? 'Government ID Verified' : 'Standard Account'}
            </span>
          </div>
        </div>
        <div className="text-xs bg-emerald-50 text-emerald-700 font-medium px-2.5 py-1 rounded-full border border-emerald-100">
          Encrypted Channel
        </div>
      </div>

      {/* In-Flight Safety Warning Banner */}
      {warning && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center space-x-2 text-xs text-amber-800">
          <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span>{warning}</span>
        </div>
      )}

      {/* Message Stream */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gray-50/30">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.isSelf ? 'items-end' : 'items-start'}`}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
                msg.isSelf
                  ? 'bg-indigo-600 text-white rounded-tr-none'
                  : 'bg-white text-gray-900 border border-gray-100 rounded-tl-none'
              }`}
            >
              {msg.content}
            </div>
            <span className="text-[10px] text-gray-400 mt-1 px-1">{msg.createdAt}</span>
          </div>
        ))}
      </div>

      {/* Input Box */}
      <form onSubmit={handleSend} className="p-4 border-t border-gray-100 bg-white flex items-center space-x-3">
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Type your message securely..."
          className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          type="submit"
          className="p-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
};
