"use client";

import React, { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorState, LoadingIndicator, Modal, Select } from "@flatmate/ui";
import { useApiQuery } from "@/hooks/useApiQuery";
import { apiClient } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { NOTE_MAX, decisionProblem, requestStatusLabel, requestTone, roleLabel } from "@/lib/role-request-model";

interface AdminRoleRequest {
  id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  user_roles: string[];
  role: string;
  status: string;
  note: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
}

const PAGE = 50;
const FILTERS = [
  { value: "pending", label: "Waiting for review" },
  { value: "approved", label: "Approved" },
  { value: "declined", label: "Not approved" },
];

/** Broker requests: approve (the role is granted at once) or decline with a reason the member sees. */
export function RoleRequestsPanel({ onDone }: { onDone: (message: string) => void }) {
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(0);
  const [deciding, setDeciding] = useState<{ request: AdminRoleRequest; approve: boolean } | null>(null);
  const list = useApiQuery<AdminRoleRequest[]>("/admin/role-requests", { status, limit: PAGE, offset: page * PAGE });
  const rows = list.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <p className="text-xs text-charcoal-muted max-w-xl">
          Members ask to be listed as brokers from their profile. Check the agency and RERA details in the note
          before approving. A decline reason is shown to the member.
        </p>
        <div className="sm:w-56">
          <Select
            aria-label="Filter requests"
            options={FILTERS}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(0);
            }}
          />
        </div>
      </div>

      {list.error && !list.isLoading ? (
        <ErrorState title="Couldn't load requests" message={list.error.message} onRetry={list.refetch} />
      ) : list.isLoading ? (
        <div className="flex justify-center py-8">
          <LoadingIndicator text="Loading requests…" />
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          title={status === "pending" ? "No requests waiting" : "Nothing here yet"}
          description={status === "pending" ? "New broker requests show up here." : "Decided requests are listed here."}
        />
      ) : (
        <div className="space-y-3">
          {rows.map((r) => (
            <Card
              key={r.id}
              data-testid="role-request"
              className="p-4 border-slate-200/80 flex flex-col md:flex-row md:items-start justify-between gap-3"
            >
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={requestTone(r.status)}>{requestStatusLabel(r.status)}</Badge>
                  <span className="text-sm font-bold text-charcoal">{roleLabel(r.role)} access</span>
                </div>
                <p className="text-xs text-charcoal">
                  <span className="font-semibold">{r.user_name}</span>{" "}
                  <span className="text-charcoal-muted break-all">({r.user_email})</span>
                </p>
                <p className="text-[11px] text-charcoal-muted">
                  Holds: {r.user_roles.map(roleLabel).join(", ")} • Asked {formatDate(r.created_at)}
                  {r.decided_at ? ` • Decided ${formatDate(r.decided_at)}` : ""}
                </p>
                <p className="text-xs text-charcoal whitespace-pre-line break-words">
                  {r.note ? `“${r.note}”` : <span className="text-charcoal-muted italic">No note given.</span>}
                </p>
                {r.decision_note && (
                  <p className="text-[11px] text-charcoal-muted break-words">Decision note: {r.decision_note}</p>
                )}
              </div>
              {r.status === "pending" && (
                <div className="flex gap-2 self-end md:self-center shrink-0">
                  <Button
                    size="sm"
                    variant="outline"
                    className="min-h-[44px] text-rose-600 border-rose-200 hover:bg-rose-50"
                    onClick={() => setDeciding({ request: r, approve: false })}
                  >
                    Decline
                  </Button>
                  <Button
                    size="sm"
                    variant="primary"
                    className="min-h-[44px]"
                    onClick={() => setDeciding({ request: r, approve: true })}
                  >
                    Approve
                  </Button>
                </div>
              )}
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

      {deciding && (
        <DecisionDialog
          request={deciding.request}
          approve={deciding.approve}
          onClose={() => setDeciding(null)}
          onDecided={(updated) => {
            // It leaves the "waiting" list; the other lists pick it up when opened.
            list.setData((prev = []) => prev.filter((r) => r.id !== updated.id));
            setDeciding(null);
            onDone(
              updated.status === "approved"
                ? `${updated.user_name} is now a broker. They've been notified.`
                : `Request declined. ${updated.user_name} has been told why.`,
            );
          }}
        />
      )}
    </div>
  );
}

function DecisionDialog({
  request,
  approve,
  onClose,
  onDecided,
}: {
  request: AdminRoleRequest;
  approve: boolean;
  onClose: () => void;
  onDecided: (updated: AdminRoleRequest) => void;
}) {
  const [note, setNote] = useState("");
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const problem = decisionProblem(approve, note);
  const role = roleLabel(request.role).toLowerCase();

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (problem) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiClient<AdminRoleRequest>(`/admin/role-requests/${request.id}/decision`, {
        method: "POST",
        body: JSON.stringify({ approve, note: note.trim() || null }),
      });
      onDecided(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the decision.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={approve ? `Approve ${role} access` : `Decline ${role} access`}
      description={`${request.user_name} (${request.user_email})`}
    >
      <form onSubmit={save} className="space-y-4">
        <p className="text-xs text-charcoal-muted">
          {approve
            ? "They get the broker role now and can list properties for their clients. Seekers see them as a broker."
            : "Their account stays as it is. They can ask again after fixing what you point out."}
        </p>
        <div>
          <label htmlFor="decision-note" className="block text-sm font-medium text-charcoal mb-1">
            {approve ? "Note for other staff (optional)" : "Reason (shown to the member)"}
          </label>
          <textarea
            id="decision-note"
            rows={3}
            maxLength={NOTE_MAX}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onBlur={() => setTouched(true)}
            aria-invalid={touched && !!problem}
            aria-describedby="decision-note-help"
            className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-charcoal focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p
            id="decision-note-help"
            className={`text-[11px] mt-1 ${touched && problem ? "text-rose-600" : "text-charcoal-muted"}`}
          >
            {touched && problem
              ? problem
              : approve
                ? "Kept with the request."
                : "For example: the RERA number doesn't match the agency name."}
          </p>
        </div>
        {error && (
          <p role="alert" className="text-xs text-rose-600">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant={approve ? "primary" : "danger"} isLoading={saving}>
            {approve ? "Approve" : "Decline"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
