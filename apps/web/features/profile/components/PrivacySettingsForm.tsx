"use client";

import React, { useState } from "react";
import type { PrivacySettingsDTO } from "@flatmate/contracts";
import { Button, Card } from "@flatmate/ui";
import { apiClient } from "@/lib/api-client";
import { InlineNotice } from "@/components/states/InlineNotice";

interface PrivacySettingsFormProps {
  initial: PrivacySettingsDTO | null;
  onSaved?: (settings: PrivacySettingsDTO) => void;
}

function Toggle({ id, title, description, checked, onChange }: {
  id: string; title: string; description: string; checked: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <label htmlFor={id} className="flex items-center justify-between gap-4 p-4 bg-warm rounded-xl border border-slate-200/80 cursor-pointer">
      <span>
        <span className="block text-sm font-bold text-charcoal">{title}</span>
        <span className="block text-[11px] text-charcoal-muted">{description}</span>
      </span>
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-5 w-5 shrink-0 rounded accent-forest" />
    </label>
  );
}

export function PrivacySettingsForm({ initial, onSaved }: PrivacySettingsFormProps) {
  const [phonePublic, setPhonePublic] = useState(initial?.show_phone_publicly ?? false);
  const [allowDirectMessages, setAllowDirectMessages] = useState(initial?.allow_direct_messages ?? true);
  const [personalized, setPersonalized] = useState(initial?.personalized_ranking ?? true);
  const [isSaving, setIsSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setNotice(null);
    try {
      const updated = await apiClient<PrivacySettingsDTO>("/profiles/me/privacy", {
        method: "PUT",
        body: JSON.stringify({
          show_phone_publicly: phonePublic,
          allow_direct_messages: allowDirectMessages,
          personalized_ranking: personalized,
        }),
      });
      onSaved?.(updated);
      setNotice({ tone: "success", text: "Privacy settings saved." });
    } catch (err) {
      setNotice({ tone: "error", text: err instanceof Error ? err.message : "Failed to save privacy settings" });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="p-6 max-w-2xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-charcoal">Privacy & visibility</h2>
        <p className="text-xs text-charcoal-muted mt-1">
          Control what other users can see before a confirmed match or appointment.
        </p>
      </div>
      {notice && <InlineNotice tone={notice.tone} className="mb-4">{notice.text}</InlineNotice>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <Toggle id="pv-phone" title="Show mobile number" description="Let other verified users see your phone number." checked={phonePublic} onChange={setPhonePublic} />
        <Toggle id="pv-dm" title="Allow direct messages" description="Let anyone start a chat with you. When off, only your matches can; owners still answer your questions about their listings, and chats you already have stay open." checked={allowDirectMessages} onChange={setAllowDirectMessages} />
        <Toggle
          id="pv-ranking"
          title="Personalised listings"
          description="Use the listings you open, save and apply to, to show the best matches first. Turn off to stop recording this; your budget and move-in date still count."
          checked={personalized}
          onChange={setPersonalized}
        />
        <Button type="submit" variant="primary" isLoading={isSaving} className="w-full sm:w-auto">
          Save privacy settings
        </Button>
      </form>
    </Card>
  );
}
