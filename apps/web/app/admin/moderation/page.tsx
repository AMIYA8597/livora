"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { Card, Button, Badge, Modal, Input } from "@flatmate/ui";
import { formatDate } from "@/lib/utils";
import {
  ShieldAlert,
  ShieldCheck,
  Users,
  Building,
  CheckCircle2,
  XCircle,
  Clock,
  Check,
  X,
  Filter,
  ArrowLeft,
  FileText,
  AlertTriangle,
} from "lucide-react";

interface ModerationReport {
  id: string;
  reporter_id: string;
  target_type: "user" | "property" | "message";
  target_id: string;
  reason: string;
  description?: string;
  status: "pending" | "under_investigation" | "resolved" | "dismissed";
  created_at: string;
}

export default function AdminModerationQueuePage() {
  const { isAuthenticated, isAdmin, user } = useAuth();
  const [reports, setReports] = useState<ModerationReport[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Review modal
  const [selectedReport, setSelectedReport] = useState<ModerationReport | null>(null);
  const [reviewAction, setReviewAction] = useState<"warn_user" | "suspend_user" | "remove_listing" | "none">("warn_user");
  const [reviewNotes, setReviewNotes] = useState("");
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  const loadReports = async () => {
    try {
      setIsLoading(true);
      const data = await apiClient<ModerationReport[]>("/moderation/reports");
      setReports(data || []);
    } catch (err) {
      console.error("Failed to load moderation queue:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadReports();
    }
  }, [isAuthenticated]);

  const handleResolve = async (reportId: string, finalStatus: "resolved" | "dismissed") => {
    try {
      setIsSubmittingReview(true);
      await apiClient(`/moderation/reports/${reportId}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: finalStatus,
          action_taken: finalStatus === "resolved" ? reviewAction : "none",
        }),
      });
      setReports((prev) =>
        prev.map((r) => (r.id === reportId ? { ...r, status: finalStatus } : r))
      );
      setSelectedReport(null);
      setActionNotice(`Report ${reportId.slice(0, 8)} marked as ${finalStatus}.`);
      setTimeout(() => setActionNotice(null), 3000);
      loadReports();
    } catch (err: any) {
      alert(err.message || "Failed to update moderation report");
    } finally {
      setIsSubmittingReview(false);
    }
  };

  const filteredReports =
    statusFilter === "all"
      ? reports
      : reports.filter((r) => r.status === statusFilter);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-1.5 bg-rose-50 text-rose-700 text-xs font-semibold px-3 py-1 rounded-full mb-2">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Trust & Safety Operations</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            Moderation & Safety Queue
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Authoritative review of reported users, fake listings, advance payment scams, and harassment flags.
          </p>
        </div>

        <Link href="/admin">
          <Button variant="outline" size="sm" className="gap-2">
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Main Admin</span>
          </Button>
        </Link>
      </div>

      {actionNotice && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center space-x-2 text-xs text-emerald-800">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center space-x-3 text-xs bg-slate-50 p-3 rounded-2xl border border-slate-200/80">
        <Filter className="w-4 h-4 text-slate-400" />
        <span className="font-semibold text-slate-700">Filter Status:</span>
        {["all", "pending", "under_investigation", "resolved", "dismissed"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 rounded-lg font-medium transition-colors capitalize ${
              statusFilter === s
                ? "bg-indigo-600 text-white shadow-2xs"
                : "text-slate-600 hover:bg-slate-200/60"
            }`}
          >
            {s.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Queue Table */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-slate-100 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : filteredReports.length === 0 ? (
        <Card className="p-12 text-center border-slate-200/80">
          <ShieldCheck className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">Moderation Queue is Clean</h3>
          <p className="text-xs text-slate-400 mt-1">
            No incidents or reports currently match the selected criteria.
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredReports.map((report) => (
            <Card
              key={report.id}
              className="p-5 border-slate-200/80 flex flex-col md:flex-row md:items-center md:justify-between gap-4 hover:shadow-xs transition-shadow"
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex items-center space-x-2">
                  <Badge
                    variant={
                      report.status === "pending"
                        ? "warning"
                        : report.status === "resolved"
                        ? "success"
                        : "default"
                    }
                    size="sm"
                  >
                    {report.status.toUpperCase()}
                  </Badge>

                  <span className="text-xs font-bold text-slate-700 uppercase bg-slate-100 px-2 py-0.5 rounded">
                    {report.target_type}
                  </span>

                  <span className="text-xs text-slate-400">
                    Reported on {formatDate(report.created_at)}
                  </span>
                </div>

                <div className="flex items-center space-x-2">
                  <span className="font-bold text-slate-900 text-sm">
                    Violation: {report.reason.replace(/_/g, " ").toUpperCase()}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    [Target ID: {report.target_id.slice(0, 8)}...]
                  </span>
                </div>

                {report.description && (
                  <p className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                    {report.description}
                  </p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSelectedReport(report)}
                  className="text-xs gap-1"
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Review Incident</span>
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Incident Review Modal */}
      <Modal
        isOpen={!!selectedReport}
        onClose={() => setSelectedReport(null)}
        title="Conduct Safety Review"
        description={selectedReport ? `Incident ID: ${selectedReport.id}` : ""}
      >
        {selectedReport && (
          <div className="space-y-4 mt-2 text-xs">
            <div className="p-3 bg-slate-50 rounded-xl space-y-1">
              <div>
                <span className="font-semibold text-slate-600">Target Type:</span>{" "}
                <span className="font-bold text-slate-900 capitalize">{selectedReport.target_type}</span>
              </div>
              <div>
                <span className="font-semibold text-slate-600">Reported Reason:</span>{" "}
                <span className="font-bold text-rose-700">{selectedReport.reason}</span>
              </div>
              <div>
                <span className="font-semibold text-slate-600">Context:</span>{" "}
                <span className="text-slate-800">{selectedReport.description || "None provided"}</span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Moderation Enforcement Action
              </label>
              <select
                value={reviewAction}
                onChange={(e) => setReviewAction(e.target.value as any)}
                className="w-full text-xs border border-slate-300 rounded-xl p-2.5 bg-white"
              >
                <option value="warn_user">Issue Compliance Warning to User</option>
                <option value="suspend_user">Deactivate / Suspend Account</option>
                <option value="remove_listing">Delist / Remove Property Listing</option>
                <option value="none">No Action (False Report / No Violation)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Internal Audit Log Notes
              </label>
              <textarea
                rows={2}
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="Document verification findings for audit compliance..."
                className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs"
              />
            </div>

            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleResolve(selectedReport.id, "dismissed")}
                isLoading={isSubmittingReview}
              >
                Dismiss Report
              </Button>
              <Button
                variant="primary"
                size="sm"
                className="bg-rose-600 hover:bg-rose-700 text-white"
                onClick={() => handleResolve(selectedReport.id, "resolved")}
                isLoading={isSubmittingReview}
              >
                Apply Enforcement
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
