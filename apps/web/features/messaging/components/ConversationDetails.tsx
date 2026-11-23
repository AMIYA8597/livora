"use client";

import React, { useState } from "react";
import type { ConversationDTO } from "@flatmate/contracts";
import { Avatar, Button } from "@flatmate/ui";
import { Archive, Bell, BellOff, X } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { InlineNotice } from "@/components/states/InlineNotice";

interface ConversationDetailsProps {
  details: ConversationDTO;
  myId?: string;
  onClose: () => void;
  /** Called after a preference changed, so the inbox can refresh. */
  onChanged: () => void;
}

const TYPE_LABEL: Record<string, string> = {
  direct: "Direct message",
  property_inquiry: "Property enquiry",
  application_linked: "Application",
  group: "Group",
  flatmate_match: "Flatmate match",
};

export function ConversationDetails({ details, myId, onClose, onChanged }: ConversationDetailsProps) {
  const [prefs, setPrefs] = useState({
    is_muted: Boolean(details.preferences?.is_muted),
    is_archived: Boolean(details.preferences?.is_archived),
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = async (patch: Partial<typeof prefs>) => {
    setBusy(true);
    setError(null);
    try {
      await apiClient(`/messaging/conversations/${details.id}/preferences`, { method: "PATCH", body: JSON.stringify(patch) });
      setPrefs((p) => ({ ...p, ...patch }));
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save that");
    } finally {
      setBusy(false);
    }
  };

  const people = details.participant_details ?? [];

  return (
    <div className="absolute inset-0 z-10 md:static md:w-72 border-l border-slate-200 bg-slate-50 md:bg-slate-50/70 p-4 flex flex-col overflow-y-auto">
      <div className="flex items-center justify-between pb-3 border-b border-slate-200">
        <h2 className="font-bold text-sm text-slate-900">Details</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close details"
          className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] -mr-2 text-slate-400 hover:text-slate-700"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <dl className="py-4 border-b border-slate-200 text-xs">
        <dt className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Type</dt>
        <dd className="font-semibold text-slate-800 mt-0.5">{TYPE_LABEL[details.type] ?? details.type}</dd>
        {details.title && (
          <>
            <dt className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mt-3">About</dt>
            <dd className="text-slate-700 mt-0.5">{details.title}</dd>
          </>
        )}
      </dl>

      <div className="py-4 flex-1">
        <h3 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">People ({people.length})</h3>
        <ul className="space-y-2">
          {people.map((p) => (
            <li key={p.id} className="flex items-center justify-between bg-white p-2 rounded-lg border border-slate-200">
              <span className="flex items-center gap-2 min-w-0">
                <Avatar alt={p.user?.full_name || "User"} size="sm" />
                <span className="text-xs font-medium text-slate-800 truncate">
                  {p.user_id === myId ? "You" : p.user?.full_name || "Member"}
                </span>
              </span>
              {p.role === "admin" && (
                <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 bg-slate-100 rounded text-slate-600">Admin</span>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="pt-4 border-t border-slate-200 space-y-2">
        {error && <InlineNotice tone="error">{error}</InlineNotice>}
        <Button
          variant="outline"
          size="sm"
          disabled={busy}
          className="w-full justify-start text-xs text-slate-700 min-h-[44px]"
          onClick={() => update({ is_muted: !prefs.is_muted })}
        >
          {prefs.is_muted ? <Bell className="w-3.5 h-3.5 mr-2" /> : <BellOff className="w-3.5 h-3.5 mr-2" />}
          {prefs.is_muted ? "Unmute" : "Mute notifications and emails"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={busy}
          className="w-full justify-start text-xs text-slate-700 min-h-[44px]"
          onClick={() => update({ is_archived: !prefs.is_archived })}
        >
          <Archive className="w-3.5 h-3.5 mr-2" />
          {prefs.is_archived ? "Move back to inbox" : "Archive"}
        </Button>
      </div>
    </div>
  );
}
