"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Button, Input, Modal } from "@flatmate/ui";
import { CheckCircle2 } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { localDateInputValue } from "@/lib/utils";
import { InlineNotice } from "@/components/states/InlineNotice";

interface ApplyModalProps {
  isOpen: boolean;
  onClose: () => void;
  propertyId: string;
  roomId: string | null;
  defaultRent: number;
  currency: string;
}

/** Tenancy application. Mount with a fresh `key` per opening so the form starts clean. */
export function ApplyModal({ isOpen, onClose, propertyId, roomId, defaultRent, currency }: ApplyModalProps) {
  const [today] = useState(() => localDateInputValue());
  const [introduction, setIntroduction] = useState("");
  const [proposedRent, setProposedRent] = useState(String(defaultRent));
  const [moveInTarget, setMoveInTarget] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await apiClient("/applications", {
        method: "POST",
        body: JSON.stringify({
          property_id: propertyId,
          room_id: roomId || undefined,
          introduction,
          proposed_rent: parseFloat(proposedRent),
          move_in_target: moveInTarget,
        }),
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit application");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={roomId ? "Apply for this room" : "Apply for this place"}
      description="Introduce yourself to the landlord and propose your move-in terms."
    >
      {done ? (
        <div className="text-center py-6">
          <CheckCircle2 className="w-12 h-12 text-forest mx-auto mb-2" />
          <h3 className="font-bold text-charcoal text-base">Application sent</h3>
          <p className="text-xs text-charcoal-muted mt-1">The owner has been notified. Track it in My Space.</p>
          <div className="mt-4 flex flex-col sm:flex-row gap-2 justify-center">
            <Link href="/dashboard"><Button variant="primary" className="min-h-[44px] w-full">Go to My Space</Button></Link>
            <Button variant="ghost" className="min-h-[44px]" onClick={onClose}>Close</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          {error && <InlineNotice tone="error">{error}</InlineNotice>}
          <div>
            <label htmlFor="apply-intro" className="block text-xs font-semibold text-charcoal mb-1">
              Introduction to the landlord
            </label>
            <textarea
              id="apply-intro"
              required
              minLength={20}
              rows={4}
              value={introduction}
              onChange={(e) => setIntroduction(e.target.value)}
              placeholder="Your work, routine, and why this place suits you…"
              className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-forest"
            />
          </div>
          <Input
            label={`Proposed monthly rent (${currency})`}
            type="number"
            inputMode="numeric"
            min={1}
            required
            value={proposedRent}
            onChange={(e) => setProposedRent(e.target.value)}
          />
          <Input
            label="Move-in date"
            type="date"
            min={today}
            required
            value={moveInTarget}
            onChange={(e) => setMoveInTarget(e.target.value)}
          />
          <Button type="submit" variant="primary" className="w-full mt-2 min-h-[44px]" isLoading={isSubmitting}>
            Send application
          </Button>
        </form>
      )}
    </Modal>
  );
}
