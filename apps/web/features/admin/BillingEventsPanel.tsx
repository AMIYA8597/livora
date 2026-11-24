"use client";

import React, { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorState, LoadingIndicator } from "@flatmate/ui";
import { CheckCircle2, RotateCcw } from "lucide-react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { apiClient } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";

interface BillingEvent {
  id: string;
  provider: string;
  event_id: string;
  event_type: string;
  status: string;
  error: string | null;
  subscription_ref: string | null;
  received_at: string;
  processed_at: string | null;
}

/**
 * Payment webhooks that failed or never finished. Each was verified and stored when it arrived,
 * so once the cause is fixed an admin can apply it again here instead of waiting for Razorpay's
 * retries. Already-applied events can't be replayed.
 */
export function BillingEventsPanel({ onDone }: { onDone: (message: string) => void }) {
  const list = useApiQuery<BillingEvent[]>("/admin/billing-events");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const replay = async (ev: BillingEvent) => {
    setBusyId(ev.id);
    setProblem(null);
    try {
      const updated = await apiClient<BillingEvent>(`/admin/billing-events/${ev.id}/replay`, { method: "POST" });
      if (updated.status === "failed") {
        setProblem(`Replay failed again: ${updated.error ?? "unknown error"}`);
        list.setData((prev = []) => prev.map((e) => (e.id === ev.id ? updated : e)));
      } else {
        list.setData((prev = []) => prev.filter((e) => e.id !== ev.id));
        onDone(`Payment event ${ev.event_type} applied (${updated.status}).`);
      }
    } catch (err: any) {
      setProblem(err?.message || "Replay failed");
      list.refetch();
    } finally {
      setBusyId(null);
    }
  };

  if (list.isLoading) return <LoadingIndicator text="Loading payment events…" />;
  if (list.error) return <ErrorState title="Payment events failed to load" message={list.error.message} onRetry={list.refetch} />;

  const rows = list.data ?? [];
  return (
    <div className="space-y-3">
      {problem && (
        <p role="alert" className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700">{problem}</p>
      )}
      {rows.length === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title="No payment events need attention"
          description="Every Razorpay webhook received so far has been applied."
        />
      ) : (
        rows.map((ev) => (
          <Card key={ev.id} className="p-5 border-slate-200/80 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={ev.status === "failed" ? "danger" : "warning"} className="capitalize">
                  {ev.status === "received" ? "Not finished" : ev.status}
                </Badge>
                <span className="text-xs font-bold text-charcoal">{ev.event_type}</span>
                {ev.subscription_ref && (
                  <span className="text-[11px] text-charcoal-muted font-mono">{ev.subscription_ref}</span>
                )}
              </div>
              {ev.error && <p className="text-xs text-rose-700 break-words">{ev.error}</p>}
              <p className="text-[11px] text-charcoal-muted">
                Received {formatDate(ev.received_at)} • <span className="font-mono">{ev.event_id}</span>
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="gap-1 min-h-[44px] self-end md:self-center"
              isLoading={busyId === ev.id}
              disabled={busyId !== null}
              onClick={() => replay(ev)}
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Apply again</span>
            </Button>
          </Card>
        ))
      )}
    </div>
  );
}
