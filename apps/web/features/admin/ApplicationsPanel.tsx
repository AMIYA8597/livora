"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Badge, Button, Card, EmptyState, ErrorState, Input, LoadingIndicator, Modal, Select } from "@flatmate/ui";
import { History, Search } from "lucide-react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { apiClient } from "@/lib/api-client";
import { formatDate, formatCurrency } from "@/lib/utils";
import {
  APPLICATION_STATUSES,
  REASON_MAX,
  overrideTargets,
  reasonProblem,
  statusLabel,
  statusTone,
} from "@/lib/admin-applications-model";

interface AdminApplication {
  id: string;
  status: string;
  applicant_id: string;
  applicant_name: string;
  applicant_email: string;
  property_id: string;
  property_title: string;
  owner_name: string | null;
  proposed_rent: number | string;
  submitted_at: string;
  updated_at: string;
}

interface StatusEvent {
  id: string;
  actor_name: string | null;
  from_status: string;
  to_status: string;
  note: string | null;
  by_staff: boolean;
  created_at: string;
}

const PAGE = 25;
const FILTERS = [{ value: "", label: "All statuses" }].concat(
  APPLICATION_STATUSES.filter((s) => s !== "reviewing" && s !== "approved").map((s) => ({
    value: s,
    label: statusLabel(s),
  })),
);

/** Find any application and, with a reason, change its status. Owners and applicants are told it was support. */
export function ApplicationsPanel({ onDone }: { onDone: (message: string) => void }) {
  const [draft, setDraft] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [editing, setEditing] = useState<AdminApplication | null>(null);

  const params: Record<string, string | number> = { limit: PAGE, offset: page * PAGE };
  if (search) params.q = search;
  if (status) params.status = status;
  const list = useApiQuery<AdminApplication[]>("/admin/applications", params);
  const rows = list.data ?? [];

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(draft.trim());
    setPage(0);
  };

  return (
    <div className="space-y-4">
      <form onSubmit={submitSearch} className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1">
          <Input
            aria-label="Search applications"
            placeholder="Listing title, applicant name or email"
            value={draft}
            maxLength={100}
            onChange={(e) => setDraft(e.target.value)}
          />
        </div>
        <div className="sm:w-48">
          <Select
            aria-label="Filter by status"
            options={FILTERS}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(0);
            }}
          />
        </div>
        <Button type="submit" variant="primary" className="gap-1.5 min-h-[44px]">
          <Search className="w-4 h-4" aria-hidden="true" /> Search
        </Button>
      </form>

      {list.error && !list.isLoading ? (
        <ErrorState title="Couldn't load applications" message={list.error.message} onRetry={list.refetch} />
      ) : list.isLoading ? (
        <div className="flex justify-center py-8">
          <LoadingIndicator text="Loading applications…" />
        </div>
      ) : rows.length === 0 ? (
        <EmptyState title="No applications found" description="Try another search or status." />
      ) : (
        <div className="space-y-3">
          {rows.map((a) => (
            <Card key={a.id} className="p-4 border-slate-200/80 flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={statusTone(a.status)}>{statusLabel(a.status)}</Badge>
                  <Link href={`/properties/${a.property_id}`} className="font-bold text-sm text-charcoal hover:underline truncate">
                    {a.property_title}
                  </Link>
                </div>
                <p className="text-xs text-charcoal">
                  <span className="font-semibold">{a.applicant_name}</span>{" "}
                  <span className="text-charcoal-muted break-all">({a.applicant_email})</span>
                </p>
                <p className="text-[11px] text-charcoal-muted">
                  Owner: {a.owner_name ?? "Unknown"} • Offered {formatCurrency(Number(a.proposed_rent), "INR")}/mo •
                  Applied {formatDate(a.submitted_at)} • Updated {formatDate(a.updated_at)}
                </p>
              </div>
              <Button size="sm" variant="outline" className="min-h-[44px] whitespace-nowrap self-end md:self-center" onClick={() => setEditing(a)}>
                Change status
              </Button>
            </Card>
          ))}
        </div>
      )}

      {(page > 0 || rows.length === PAGE) && (
        <div className="flex justify-between">
          <Button variant="ghost" size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
            Previous
          </Button>
          <Button variant="ghost" size="sm" disabled={rows.length < PAGE} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      )}

      {editing && (
        <OverrideDialog
          application={editing}
          onClose={() => setEditing(null)}
          onSaved={(updated) => {
            list.setData((prev = []) => prev.map((a) => (a.id === updated.id ? { ...a, ...updated } : a)));
            setEditing(null);
            onDone(`Application moved to ${statusLabel(updated.status)}. The applicant and owner were notified.`);
          }}
        />
      )}
    </div>
  );
}

function OverrideDialog({
  application,
  onClose,
  onSaved,
}: {
  application: AdminApplication;
  onClose: () => void;
  onSaved: (updated: Pick<AdminApplication, "id" | "status" | "updated_at">) => void;
}) {
  const targets = overrideTargets(application.status);
  const [target, setTarget] = useState<string>(targets[0] ?? "");
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const history = useApiQuery<StatusEvent[]>(`/admin/applications/${application.id}/history`);
  const problem = reasonProblem(reason);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (problem || !target) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiClient<AdminApplication>(`/applications/${application.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: target, note: reason.trim() }),
      });
      onSaved({ id: updated.id, status: updated.status, updated_at: updated.updated_at });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't change the status.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Change application status"
      description={`${application.applicant_name} → ${application.property_title}`}
    >
      <form onSubmit={save} className="space-y-4">
        <p className="text-xs text-charcoal-muted">
          Now: <Badge variant={statusTone(application.status)} size="sm">{statusLabel(application.status)}</Badge>
        </p>
        <Select
          label="New status"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          options={targets.map((s) => ({ value: s, label: statusLabel(s) }))}
        />
        <div>
          <label htmlFor="override-reason" className="block text-sm font-medium text-charcoal mb-1">
            Reason (staff only)
          </label>
          <textarea
            id="override-reason"
            rows={3}
            maxLength={REASON_MAX}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            onBlur={() => setTouched(true)}
            aria-invalid={touched && !!problem}
            aria-describedby="override-reason-help"
            className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-charcoal focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p id="override-reason-help" className={`text-[11px] mt-1 ${touched && problem ? "text-rose-600" : "text-charcoal-muted"}`}>
            {touched && problem
              ? problem
              : "Kept in the application's history. The applicant and owner are told Flatmate support made the change, not why."}
          </p>
        </div>

        <section aria-label="Status history" className="border-t border-slate-100 pt-3">
          <h3 className="text-xs font-bold text-charcoal flex items-center gap-1.5 mb-2">
            <History className="w-3.5 h-3.5" aria-hidden="true" /> History
          </h3>
          {history.isLoading ? (
            <p className="text-[11px] text-charcoal-muted">Loading…</p>
          ) : history.error ? (
            <p className="text-[11px] text-rose-600">{history.error.message}</p>
          ) : !history.data?.length ? (
            <p className="text-[11px] text-charcoal-muted">No changes yet.</p>
          ) : (
            <ol className="space-y-1.5 max-h-40 overflow-y-auto">
              {history.data.map((h) => (
                <li key={h.id} className="text-[11px] text-charcoal">
                  <span className="font-semibold">
                    {statusLabel(h.from_status)} → {statusLabel(h.to_status)}
                  </span>{" "}
                  <span className="text-charcoal-muted">
                    by {h.actor_name ?? "a deleted account"}
                    {h.by_staff ? " (support)" : ""}, {formatDate(h.created_at)}
                  </span>
                  {h.note && <span className="block text-charcoal-muted italic">“{h.note}”</span>}
                </li>
              ))}
            </ol>
          )}
        </section>

        {error && (
          <p role="alert" className="text-xs text-rose-600">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" isLoading={saving} disabled={!target}>
            Change status
          </Button>
        </div>
      </form>
    </Modal>
  );
}
