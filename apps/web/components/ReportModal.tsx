"use client";

import React, { useState } from "react";
import { Modal, Button, Input } from "@flatmate/ui";
import { ShieldAlert, CheckCircle2 } from "lucide-react";
import { apiClient } from "@/lib/api-client";

export interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetType: "user" | "property" | "message";
  targetId: string;
  targetName?: string;
}

export const ReportModal: React.FC<ReportModalProps> = ({
  isOpen,
  onClose,
  targetType,
  targetId,
  targetName,
}) => {
  const [reason, setReason] = useState("harassment");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await apiClient("/moderation/reports", {
        method: "POST",
        body: JSON.stringify({
          target_type: targetType,
          target_id: targetId,
          reason,
          description: description || undefined,
        }),
      });
      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        setDescription("");
        onClose();
      }, 2000);
    } catch (err: any) {
      setError(err.message || "Failed to submit moderation report");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Report ${targetType === "user" ? "User" : targetType === "property" ? "Property Listing" : "Message"}`}
      description={
        targetName
          ? `Submit an issue or safety violation regarding ${targetName}.`
          : "Our trust & safety team reviews all reports within 24 hours."
      }
    >
      {success ? (
        <div className="py-8 text-center space-y-3">
          <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-2xl flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h4 className="font-bold text-slate-900 text-base">Report Submitted</h4>
          <p className="text-xs text-slate-500">
            Thank you for helping keep Flatmate safe. Our team is investigating this issue.
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Reason for Report</label>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {targetType === "property" ? (
                <>
                  <option value="fake_listing">Fake or Fraudulent Listing</option>
                  <option value="advance_scam">Demanding Advance Payment before Visit</option>
                  <option value="misleading_photos">Misleading Images or Location</option>
                  <option value="discriminatory_policy">Unlawful Discrimination</option>
                  <option value="already_rented">Property No Longer Available</option>
                </>
              ) : targetType === "message" ? (
                <>
                  <option value="advance_scam">Rental Payment / Advance Scam</option>
                  <option value="harassment">Harassment or Inappropriate Conduct</option>
                  <option value="spam">Commercial Spam / Unsolicited Promotion</option>
                  <option value="contact_harvesting">Unauthorized Contact Harvesting</option>
                </>
              ) : (
                <>
                  <option value="harassment">Harassment or Abusive Behavior</option>
                  <option value="impersonation">Fake Identity or Impersonation</option>
                  <option value="advance_scam">Financial Fraud / Advance Scam</option>
                  <option value="inappropriate_content">Inappropriate Profile Content</option>
                  <option value="dealbreaker_misrepresentation">Misrepresenting Lifestyle / Dealbreakers</option>
                </>
              )}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Details & Context (Optional)
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Provide specific details to help our safety moderation team investigate..."
              className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="flex justify-end space-x-2 pt-2">
            <Button type="button" variant="ghost" size="sm" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isSubmitting}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              Submit Report
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
};
