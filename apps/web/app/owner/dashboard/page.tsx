"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { useApiQuery } from "@/hooks/useApiQuery";
import { apiClient } from "@/lib/api-client";
import { OwnerDashboardStatsDTO, ApplicantReviewCardDTO } from "@flatmate/contracts";
import { Card, Button, Badge, Modal, Avatar, ErrorState } from "@flatmate/ui";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  Building,
  Users,
  CheckCircle2,
  XCircle,
  Plus,
  Home,
  IndianRupee,
  Clock,
  Check,
  X,
  FileText,
  Calendar,
  Layers,
  Bed,
} from "lucide-react";

export default function OwnerDashboardPage() {
  const { isAuthenticated, isLoading: authLoading, isOwner, isAdmin, user } = useAuth();
  const statsQuery = useApiQuery<OwnerDashboardStatsDTO>(isAuthenticated ? "/owners/dashboard" : null);
  const applicationsQuery = useApiQuery<ApplicantReviewCardDTO[]>(isAuthenticated ? "/owners/applications" : null);
  const stats = statsQuery.data ?? null;
  const applications = applicationsQuery.data ?? [];
  const setApplications = applicationsQuery.setData;
  const isLoading = authLoading || applicationsQuery.isLoading;
  const loadOwnerData = () => {
    statsQuery.refetch();
    applicationsQuery.refetch();
  };
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const handleUpdateStatus = async (appId: string, newStatus: "approved" | "rejected") => {
    try {
      await apiClient(`/owners/applications/${appId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      setApplications((prev = []) =>
        prev.map((a) => ((a.application_id || a.id) === appId ? { ...a, status: newStatus } : a))
      );
      setActionNotice(`Application successfully ${newStatus}!`);
      setTimeout(() => setActionNotice(null), 3000);
      loadOwnerData();
    } catch (err: any) {
      alert(err.message || "Failed to update application status");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-1.5 bg-indigo-50 text-indigo-700 text-xs font-semibold px-3 py-1 rounded-full mb-2">
            <Building className="w-3.5 h-3.5" />
            <span>Landlord & Property Portal</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Owner Dashboard</h1>
          <p className="text-slate-500 text-sm mt-1">
            Real-time management of properties, inventory availability, tenancy applications, and visits.
          </p>
        </div>

        <Link href="/owner/listings/create">
          <Button variant="primary" className="gap-2 shadow-md">
            <Plus className="w-4 h-4" />
            <span>List New Property (Wizard)</span>
          </Button>
        </Link>
      </div>

      {actionNotice && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center space-x-2 text-xs text-emerald-800">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Real Statistics Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <Card className="p-4 border-slate-200/80 bg-white shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase block">Total Properties</span>
          <span className="text-2xl font-black text-slate-900 mt-1 block">
            {stats ? stats.total_properties : 0}
          </span>
          <span className="text-[10px] text-slate-400 mt-0.5 block">Managed on platform</span>
        </Card>

        <Card className="p-4 border-slate-200/80 bg-white shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase block">Active Listings</span>
          <span className="text-2xl font-black text-emerald-600 mt-1 block">
            {stats ? stats.active_listings : 0}
          </span>
          <span className="text-[10px] text-emerald-600/80 mt-0.5 block">Live in search</span>
        </Card>

        <Card className="p-4 border-slate-200/80 bg-white shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase block">Available Rooms</span>
          <span className="text-2xl font-black text-indigo-600 mt-1 block">
            {stats ? stats.available_rooms : 0}
          </span>
          <span className="text-[10px] text-slate-400 mt-0.5 block">Vacant rooms</span>
        </Card>

        <Card className="p-4 border-slate-200/80 bg-white shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase block">Available Beds</span>
          <span className="text-2xl font-black text-purple-600 mt-1 block">
            {stats ? stats.available_beds : 0}
          </span>
          <span className="text-[10px] text-slate-400 mt-0.5 block">Ready to occupy</span>
        </Card>

        <Card className="p-4 border-slate-200/80 bg-white shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase block">Applications</span>
          <span className="text-2xl font-black text-amber-600 mt-1 block">
            {stats ? stats.total_applications : 0}
          </span>
          <span className="text-[10px] text-amber-600/80 mt-0.5 block">Pending review</span>
        </Card>

        <Card className="p-4 border-slate-200/80 bg-white shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase block">Total Revenue</span>
          <span className="text-2xl font-black text-slate-900 mt-1 block">
            {formatCurrency(stats ? stats.monthly_rental_value : 0, "INR")}
          </span>
          <span className="text-[10px] text-slate-400 mt-0.5 block">Monthly contracted</span>
        </Card>
      </div>

      {/* Tenancy Applications Queue */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">Incoming Tenant Applications</h2>
          <Badge variant="info" size="sm">
            {applications.length} Received
          </Badge>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-32 bg-slate-100 rounded-2xl animate-pulse" />
            ))}
          </div>
        ) : applicationsQuery.error || statsQuery.error ? (
          <ErrorState
            title="Couldn't load your portal"
            message={(applicationsQuery.error || statsQuery.error)?.message}
            onRetry={loadOwnerData}
          />
        ) : applications.length === 0 ? (
          <Card className="p-12 text-center border-slate-200/80">
            <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="font-semibold text-slate-800 text-sm">No applications pending review</h3>
            <p className="text-xs text-slate-400 mt-1">
              When seekers apply for your listings or rooms, their applications with compatibility breakdown will appear here.
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {applications.map((app) => (
              <Card key={app.application_id || app.id} className="p-5 border-slate-200/80 space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <Avatar alt={app.applicant_name} size="md" />
                    <div>
                      <h4 className="font-bold text-slate-900 text-sm">{app.applicant_name}</h4>
                      <p className="text-xs text-slate-500">{app.property_title}</p>
                    </div>
                  </div>
                  <Badge
                    variant={
                      app.status === "approved"
                        ? "success"
                        : app.status === "rejected"
                        ? "danger"
                        : "warning"
                    }
                    size="sm"
                  >
                    {app.status.toUpperCase()}
                  </Badge>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs bg-slate-50 p-3 rounded-xl border border-slate-100">
                  <div>
                    <span className="text-slate-400 block text-[10px]">Offered Rent:</span>
                    <span className="font-bold text-slate-800">{formatCurrency(app.proposed_rent, "INR")}/mo</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">Target Move-In:</span>
                    <span className="font-semibold text-slate-800">{formatDate(app.move_in_target)}</span>
                  </div>
                </div>

                {app.introduction && (
                  <p className="text-xs text-slate-600 bg-slate-50/50 p-2.5 rounded-lg italic border border-slate-100">
                    &ldquo;{app.introduction}&rdquo;
                  </p>
                )}

                {app.status === "pending" && (
                  <div className="flex items-center space-x-2 pt-2 border-t border-slate-100">
                    <Button
                      size="sm"
                      variant="primary"
                      className="flex-1 gap-1.5 bg-emerald-600 hover:bg-emerald-700"
                      onClick={() => handleUpdateStatus(app.application_id || app.id!, "approved")}
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Accept Tenant</span>
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1 gap-1.5 text-rose-600 border-rose-200 hover:bg-rose-50"
                      onClick={() => handleUpdateStatus(app.application_id || app.id!, "rejected")}
                    >
                      <X className="w-3.5 h-3.5" />
                      <span>Decline</span>
                    </Button>
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
