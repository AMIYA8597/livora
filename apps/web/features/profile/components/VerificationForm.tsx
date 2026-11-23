"use client";

import React, { useState } from "react";
import type { UserTrustStatusDTO } from "@flatmate/contracts";
import { Button } from "@flatmate/ui";
import { apiClient } from "@/lib/api-client";
import { InlineNotice } from "@/components/states/InlineNotice";

export const VERIFICATION_TYPES = [
  { value: "government_id", label: "Government ID (Aadhaar / Passport / DL)" },
  { value: "work_email", label: "Corporate work email / offer letter" },
  { value: "student_email", label: "University / student ID" },
];

interface VerificationFormProps {
  /** Called with the refreshed trust status after a successful submission. */
  onSubmitted?: (status: UserTrustStatusDTO | null) => void;
}

/**
 * Request identity verification. The document itself is not collected here yet: identity
 * verification is still mocked (launch gap item 12), so this records the request only.
 */
export function VerificationForm({ onSubmitted }: VerificationFormProps) {
  const [type, setType] = useState(VERIFICATION_TYPES[0].value);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setNotice(null);
    try {
      await apiClient("/verification/submit", {
        method: "POST",
        body: JSON.stringify({
          verification_type: type,
          document_url: "https://documents.flatmate.platform/v/pending_upload.pdf",
        }),
      });
      const status = await apiClient<UserTrustStatusDTO>("/verification/status").catch(() => null);
      onSubmitted?.(status);
      setNotice({ tone: "success", text: "Submitted. Our team will review it shortly." });
    } catch (err) {
      setNotice({ tone: "error", text: err instanceof Error ? err.message : "Verification submission failed" });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {notice && <InlineNotice tone={notice.tone}>{notice.text}</InlineNotice>}
      <div>
        <label htmlFor="verify-type" className="block text-xs font-semibold text-charcoal mb-1">Verification type</label>
        <select
          id="verify-type"
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="w-full min-h-[44px] text-sm rounded-xl border border-slate-200 px-2.5 bg-white"
        >
          {VERIFICATION_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>
      <Button type="submit" variant="primary" isLoading={isSubmitting} className="w-full sm:w-auto">
        Submit for verification
      </Button>
    </form>
  );
}
