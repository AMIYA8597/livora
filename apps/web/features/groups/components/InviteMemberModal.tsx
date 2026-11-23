"use client";

import React, { useState } from "react";
import { Button, Input, Modal } from "@flatmate/ui";
import { CheckCircle2 } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { InlineNotice } from "@/components/states/InlineNotice";

interface InviteMemberModalProps {
  groupId: string;
  groupName: string;
  onClose: () => void;
  onAdded: () => void;
}

/**
 * Add someone by their Flatmate user ID. There is no user search API yet, so the ID is the only
 * handle; the person can find it on their profile page.
 */
export function InviteMemberModal({ groupId, groupName, onClose, onAdded }: InviteMemberModalProps) {
  const [userId, setUserId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await apiClient(`/groups/${groupId}/members`, {
        method: "POST",
        body: JSON.stringify({ user_id: userId.trim(), role: "member" }),
      });
      setDone(true);
      onAdded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add that person");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen onClose={onClose} title={`Add someone to ${groupName}`} description="Ask them for the user ID shown on their profile.">
      {done ? (
        <div className="text-center py-6">
          <CheckCircle2 className="w-12 h-12 text-forest mx-auto mb-2" />
          <h3 className="font-bold text-charcoal text-base">Added to the group</h3>
          <Button variant="ghost" className="mt-4" onClick={onClose}>Close</Button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          {error && <InlineNotice tone="error">{error}</InlineNotice>}
          <Input
            label="Their user ID"
            required
            pattern="[0-9a-fA-F-]{36}"
            title="A user ID looks like 550e8400-e29b-41d4-a716-446655440000"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
          />
          <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSubmitting}>
            Add to group
          </Button>
        </form>
      )}
    </Modal>
  );
}
