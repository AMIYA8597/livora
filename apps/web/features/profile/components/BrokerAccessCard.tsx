"use client";

import React, { useState } from "react";
import { Badge, Button, Card } from "@flatmate/ui";
import { BadgeCheck, Briefcase } from "lucide-react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { apiClient } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { NOTE_MAX, brokerAccess, type RoleRequest } from "@/lib/role-request-model";

/**
 * Ask to be listed as a broker. Flatmate checks the agency details first, so seekers can trust
 * the broker badge; an admin approves, or declines with a reason shown here.
 */
export function BrokerAccessCard({ roles, onNotice }: { roles: readonly string[]; onNotice: (message: string) => void }) {
  const requests = useApiQuery<RoleRequest[]>("/users/me/role-requests");
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const access = brokerAccess(roles, requests.data ?? []);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setSending(true);
    setError(null);
    try {
      const created = await apiClient<RoleRequest>("/users/me/role-requests", {
        method: "POST",
        body: JSON.stringify({ role: "broker", note: note.trim() || null }),
      });
      requests.setData((prev = []) => [created, ...prev]);
      setNote("");
      onNotice("Request sent. We'll let you know once it's reviewed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send the request.");
    } finally {
      setSending(false);
    }
  };

  return (
    <Card className="p-6 max-w-2xl" aria-labelledby="broker-access-title">
      <div className="flex items-start gap-3 mb-4">
        <Briefcase className="w-6 h-6 text-forest shrink-0 mt-0.5" aria-hidden="true" />
        <div>
          <h2 id="broker-access-title" className="text-lg font-bold text-charcoal">
            Broker access
          </h2>
          <p className="text-xs text-charcoal-muted mt-1">
            Letting or managing homes for clients? Brokers are checked by Flatmate before they can list, and
            seekers see a broker badge on their listings.
          </p>
        </div>
      </div>

      {requests.isLoading ? (
        <p className="text-xs text-charcoal-muted">Loading…</p>
      ) : requests.error ? (
        <p className="text-xs text-rose-600">
          {requests.error.message}{" "}
          <button type="button" className="underline" onClick={requests.refetch}>
            Try again
          </button>
        </p>
      ) : access.state === "broker" ? (
        <p className="flex items-center gap-2 text-sm font-semibold text-forest">
          <BadgeCheck className="w-5 h-5" aria-hidden="true" /> You’re a verified broker.
        </p>
      ) : access.state === "pending" ? (
        <div className="space-y-1" data-testid="broker-request-status">
          <Badge variant="warning">Waiting for review</Badge>
          <p className="text-xs text-charcoal-muted">
            Sent {formatDate(access.request.created_at)}. We’ll notify you when it’s decided.
          </p>
        </div>
      ) : (
        <form onSubmit={send} className="space-y-3">
          {access.state === "declined" && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-100 text-xs text-rose-800" data-testid="broker-request-status">
              <p className="font-semibold">Your last request wasn’t approved.</p>
              {access.request.decision_note && <p className="mt-1">Reason: {access.request.decision_note}</p>}
              <p className="mt-1">You can ask again once that’s sorted.</p>
            </div>
          )}
          <div>
            <label htmlFor="broker-note" className="block text-sm font-medium text-charcoal mb-1">
              About your work
            </label>
            <textarea
              id="broker-note"
              rows={3}
              maxLength={NOTE_MAX}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              aria-describedby="broker-note-help"
              className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-charcoal focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <p id="broker-note-help" className="text-[11px] text-charcoal-muted mt-1">
              Agency name, RERA registration number and the cities you work in. Only Flatmate staff see this.
            </p>
          </div>
          {error && (
            <p role="alert" className="text-xs text-rose-600">
              {error}
            </p>
          )}
          <Button type="submit" variant="primary" isLoading={sending}>
            Request broker access
          </Button>
        </form>
      )}
    </Card>
  );
}
