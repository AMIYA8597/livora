"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Modal } from "@flatmate/ui";
import { LISTING_QUICK_QUESTIONS, type ListingQuickQuestionKey, type StartListingChatResponse } from "@flatmate/contracts";
import { ShieldCheck } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { ASK_MAX_CHARS, composeOwnerQuestion } from "@/lib/ask-owner";
import { InlineNotice } from "@/components/states/InlineNotice";

interface AskOwnerModalProps {
  isOpen: boolean;
  onClose: () => void;
  propertyId: string;
  listingTitle: string;
}

/**
 * "Ask the owner": quick questions and/or the person's own words, sent as the first message of
 * the chat about this listing (an existing chat about it is reused). Opens the chat after.
 */
export function AskOwnerModal({ isOpen, onClose, propertyId, listingTitle }: AskOwnerModalProps) {
  const router = useRouter();
  const [chosen, setChosen] = useState<ListingQuickQuestionKey[]>([]);
  const [own, setOwn] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const message = composeOwnerQuestion(LISTING_QUICK_QUESTIONS, chosen, own);
  const tooLong = message.length > ASK_MAX_CHARS;

  const toggle = (key: ListingQuickQuestionKey) =>
    setChosen((cur) => (cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key]));

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (tooLong) return;
    setIsSending(true);
    setError(null);
    try {
      const res = await apiClient<StartListingChatResponse>("/messaging/listing-chats", {
        method: "POST",
        body: JSON.stringify({ property_id: propertyId, content: message }),
      });
      router.push(`/messages?conversationId=${encodeURIComponent(res.conversation_id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't reach the owner. Try again.");
      setIsSending(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Ask the owner" description={listingTitle}>
      <form onSubmit={send} className="space-y-4">
        <fieldset>
          <legend className="text-xs font-semibold text-charcoal mb-2">Quick questions</legend>
          <div className="flex flex-wrap gap-2">
            {LISTING_QUICK_QUESTIONS.map((q) => {
              const on = chosen.includes(q.key);
              return (
                <button
                  key={q.key}
                  type="button"
                  aria-pressed={on}
                  title={q.text}
                  onClick={() => toggle(q.key)}
                  className={`min-h-[40px] px-3 text-xs font-semibold rounded-full border transition-all ${
                    on ? "bg-pale-green/40 border-forest text-forest" : "border-slate-200 text-charcoal hover:bg-slate-50"
                  }`}
                >
                  {q.label}
                </button>
              );
            })}
          </div>
        </fieldset>

        <div>
          <label htmlFor="ask-owner-text" className="text-xs font-semibold text-charcoal">
            Anything else? <span className="font-normal text-charcoal-muted">(optional)</span>
          </label>
          <textarea
            id="ask-owner-text"
            value={own}
            onChange={(e) => setOwn(e.target.value)}
            rows={3}
            maxLength={ASK_MAX_CHARS}
            placeholder="e.g. I'm a working professional moving from Pune next month."
            className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-forest/30"
          />
        </div>

        {message && (
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
            <p className="text-[11px] font-semibold text-charcoal-muted mb-1">Your message</p>
            <p className="text-sm text-charcoal whitespace-pre-line">{message}</p>
          </div>
        )}

        <p className="flex items-start gap-1.5 text-xs text-charcoal-muted">
          <ShieldCheck className="w-4 h-4 shrink-0 text-forest" aria-hidden="true" />
          <span>Phone numbers and emails stay hidden in this chat until the owner confirms a visit.</span>
        </p>

        {tooLong && <InlineNotice tone="error">That&apos;s too long for a first message. Shorten it a little.</InlineNotice>}
        {error && <InlineNotice tone="error">{error}</InlineNotice>}

        <div className="flex gap-2 justify-end">
          <Button type="button" variant="ghost" onClick={onClose} className="min-h-[44px]">Cancel</Button>
          <Button type="submit" variant="primary" isLoading={isSending} disabled={tooLong} className="min-h-[44px]">
            {message ? "Send" : "Open chat"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
