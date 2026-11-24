"use client";

import React, { useId, useState } from "react";
import type { ApplicationTimelineEntryDTO } from "@flatmate/contracts";
import { ChevronDown, History } from "lucide-react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { formatDate } from "@/lib/utils";
import { timelineText, type TimelineViewer } from "@/lib/application-timeline";

/** A "History" toggle showing every status change of one application. Loads when first opened. */
export function ApplicationTimeline({ applicationId, viewer }: { applicationId: string; viewer: TimelineViewer }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const history = useApiQuery<ApplicationTimelineEntryDTO[]>(open ? `/applications/${applicationId}/history` : null);

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        className="inline-flex items-center gap-1 min-h-[44px] sm:min-h-0 text-xs font-semibold text-forest hover:underline"
      >
        <History className="w-3.5 h-3.5" aria-hidden="true" />
        History
        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>
      {open && (
        <div id={panelId} className="mt-1">
          {history.isLoading ? (
            <p className="text-[11px] text-charcoal-muted">Loading…</p>
          ) : history.error ? (
            <p role="alert" className="text-[11px] text-rose-600">{history.error.message}</p>
          ) : (
            <ol className="border-l-2 border-slate-200 pl-3 space-y-1.5">
              {(history.data ?? []).map((entry, i) => (
                <li key={`${entry.created_at}-${i}`} className="text-[11px] text-charcoal">
                  <span className="font-semibold">{timelineText(entry, viewer)}</span>
                  <span className="text-charcoal-muted"> · {formatDate(entry.created_at)}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
