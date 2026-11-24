"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Card, Modal } from "@flatmate/ui";
import { Download, Trash2 } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { signOut } from "@/lib/auth-store";
import { InlineNotice } from "@/components/states/InlineNotice";
import { deletionConsequences, exportFileName } from "@/lib/account-data-model";

interface DeletionScheduled {
  requested_at: string;
  purge_after: string;
}

/** Download everything we hold, or delete the account (30-day grace, password confirmed). */
export function DataControlsCard() {
  const router = useRouter();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const download = async () => {
    setExporting(true);
    setExportError(null);
    try {
      const data = await apiClient<unknown>("/users/me/export", { timeoutMs: 60000 });
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = exportFileName();
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Couldn't prepare your download. Please try again.");
    } finally {
      setExporting(false);
    }
  };

  const closeConfirm = () => {
    if (deleting) return;
    setConfirmOpen(false);
    setPassword("");
    setDeleteError(null);
  };

  const confirmDeletion = async (e: React.FormEvent) => {
    e.preventDefault();
    setDeleting(true);
    setDeleteError(null);
    try {
      const res = await apiClient<DeletionScheduled>("/users/me/deletion", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      await signOut();
      router.replace(`/login?deleted=${encodeURIComponent(res.purge_after)}`);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Couldn't delete your account. Please try again.");
      setDeleting(false);
    }
  };

  return (
    <Card className="p-6">
      <h2 className="text-lg font-bold text-charcoal mb-1">Your data</h2>
      <p className="text-xs text-charcoal-muted mb-4">
        Download a copy of everything Flatmate holds about you, or delete your account.
      </p>

      <div className="flex flex-col sm:flex-row gap-3">
        <Button variant="outline" onClick={download} disabled={exporting} className="min-h-[44px]">
          <Download className="w-4 h-4 mr-2" aria-hidden />
          {exporting ? "Preparing…" : "Download my data"}
        </Button>
        <Button variant="danger" onClick={() => setConfirmOpen(true)} className="min-h-[44px]">
          <Trash2 className="w-4 h-4 mr-2" aria-hidden />
          Delete my account
        </Button>
      </div>
      {exportError && <div className="mt-3"><InlineNotice tone="error">{exportError}</InlineNotice></div>}

      <Modal isOpen={confirmOpen} onClose={closeConfirm} title="Delete your account?">
        <form onSubmit={confirmDeletion} className="space-y-4">
          <ul className="list-disc pl-5 space-y-1.5 text-sm text-charcoal">
            {deletionConsequences().map((line) => <li key={line}>{line}</li>)}
          </ul>
          <div>
            <label htmlFor="delete-password" className="block text-xs font-semibold text-charcoal mb-1">
              Enter your password to confirm
            </label>
            <input
              id="delete-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm min-h-[44px] focus:outline-none focus:ring-2 focus:ring-red-500"
            />
          </div>
          {deleteError && <InlineNotice tone="error">{deleteError}</InlineNotice>}
          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
            <Button type="button" variant="ghost" onClick={closeConfirm} disabled={deleting} className="min-h-[44px]">
              Keep my account
            </Button>
            <Button type="submit" variant="danger" disabled={deleting || !password} className="min-h-[44px]">
              {deleting ? "Deleting…" : "Delete my account"}
            </Button>
          </div>
        </form>
      </Modal>
    </Card>
  );
}
