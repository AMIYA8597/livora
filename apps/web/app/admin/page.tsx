"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useApiQuery } from "@/hooks/useApiQuery";
import { apiClient } from "@/lib/api-client";
import { Card, Button, Badge, Modal, Input, EmptyState, ErrorState, LoadingIndicator } from "@flatmate/ui";
import { formatDate, formatCurrency } from "@/lib/utils";
import {
  ShieldCheck,
  ShieldAlert,
  Users,
  AlertTriangle,
  Building,
  CheckCircle2,
  XCircle,
  Clock,
  Activity,
  Check,
  X,
  Filter,
  Shield,
  Eye,
  MapPin,
  Lock,
} from "lucide-react";

interface AdminStats {
  total_users: number;
  total_properties: number;
  active_applications: number;
  open_moderation_reports: number;
}

interface ModerationReport {
  id: string;
  reporter_id: string;
  target_type: string;
  target_id: string;
  reason: string;
  description?: string;
  status: string;
  created_at: string;
}

interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

interface AdminProperty {
  id: string;
  title: string;
  address_display: string;
  city: string;
  monthly_rent: number;
  configuration: string;
  is_verified: boolean;
  listing_status: string;
  created_at: string;
}

export default function AdminModerationPage() {
  const { isAuthenticated, isLoading: authLoading, isAdmin, user } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"stats" | "moderation" | "properties" | "users">("stats");

  const canView = isAuthenticated && (isAdmin || user?.role === "super_admin" || user?.role === "admin");
  const statsQuery = useApiQuery<AdminStats>(canView ? "/admin/stats" : null);
  const reportsQuery = useApiQuery<ModerationReport[]>(canView ? "/moderation/reports" : null);
  const usersQuery = useApiQuery<AdminUser[]>(canView ? "/admin/users" : null);
  const propertiesQuery = useApiQuery<AdminProperty[]>(canView ? "/properties" : null);
  const stats = statsQuery.data ?? null;
  const reports = reportsQuery.data ?? [];
  const users = usersQuery.data ?? [];
  const properties = propertiesQuery.data ?? [];
  const setReports = reportsQuery.setData;
  const setUsers = usersQuery.setData;
  const setProperties = propertiesQuery.setData;
  const isLoading = statsQuery.isLoading || reportsQuery.isLoading || usersQuery.isLoading || propertiesQuery.isLoading;
  const loadError = statsQuery.error || reportsQuery.error || usersQuery.error || propertiesQuery.error;
  const reloadAll = () => {
    statsQuery.refetch();
    reportsQuery.refetch();
    usersQuery.refetch();
    propertiesQuery.refetch();
  };
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const handleResolveReport = async (reportId: string, status: "resolved" | "dismissed") => {
    try {
      await apiClient(`/moderation/reports/${reportId}`, {
        method: "PATCH",
        body: JSON.stringify({
          status,
          action_taken: status === "resolved" ? "Account flagged / content moderated" : "No policy violation found",
        }),
      });
      setReports((prev = []) =>
        prev.map((r) => (r.id === reportId ? { ...r, status } : r))
      );
      setActionNotice(`Report marked as ${status}.`);
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to update report");
    }
  };

  const handleToggleUserStatus = async (userId: string, currentStatus: boolean) => {
    try {
      await apiClient(`/admin/users/${userId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !currentStatus }),
      });
      setUsers((prev = []) =>
        prev.map((u) => (u.id === userId ? { ...u, is_active: !currentStatus } : u))
      );
      setActionNotice(`User account ${!currentStatus ? "activated" : "suspended"}.`);
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to update user status");
    }
  };

  const handleApproveProperty = async (propId: string) => {
    try {
      await apiClient(`/properties/${propId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ listing_status: "published" }),
      });
      setProperties((prev = []) =>
        prev.map((p) => (p.id === propId ? { ...p, is_verified: true, listing_status: "published" } : p))
      );
      setActionNotice("Property approved and published to marketplace.");
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to approve property");
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center">
        <LoadingIndicator size="lg" text="Checking access…" />
      </div>
    );
  }

  if (!canView) {
    return (
      <div className="max-w-md mx-auto py-20 px-4 text-center">
        <Card className="p-8">
          <ShieldAlert className="w-12 h-12 text-rose-600 mx-auto mb-3" />
          <h2 className="text-xl font-bold text-charcoal mb-2">Access Denied</h2>
          <p className="text-xs text-charcoal-muted mb-6">
            Administrator privileges are required to view platform metrics and the moderation queue.
          </p>
          <Button variant="primary" onClick={() => router.push("/")} className="w-full">
            Return Home
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 bg-forest-pale text-forest text-xs font-semibold px-3 py-1 rounded-full mb-2">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Platform Operations & Trust Safety</span>
          </div>
          <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">Admin & Moderation Console</h1>
          <p className="text-charcoal-muted text-sm mt-1">
            Review community safety reports, verify rental inventory and users, and monitor real-time platform health.
          </p>
        </div>
      </div>

      {loadError && !isLoading && (
        <ErrorState
          title="Some admin data failed to load"
          message={loadError.message}
          onRetry={reloadAll}
        />
      )}
      {isLoading && (
        <div className="flex justify-center py-6">
          <LoadingIndicator text="Loading console…" />
        </div>
      )}

      {actionNotice && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-2xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-200 space-x-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab("stats")}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === "stats" ? "border-forest text-forest font-bold" : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <Activity className="w-4 h-4" /> System Overview
        </button>
        <button
          onClick={() => setActiveTab("moderation")}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === "moderation" ? "border-forest text-forest font-bold" : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <AlertTriangle className="w-4 h-4" /> Moderation Queue ({reports.filter((r) => r.status === "pending").length})
        </button>
        <button
          onClick={() => setActiveTab("properties")}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === "properties" ? "border-forest text-forest font-bold" : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <Building className="w-4 h-4" /> Property Verification ({properties.length})
        </button>
        <button
          onClick={() => setActiveTab("users")}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === "users" ? "border-forest text-forest font-bold" : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <Users className="w-4 h-4" /> User Management ({users.length})
        </button>
      </div>

      {/* Tab 1: Stats */}
      {activeTab === "stats" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="p-5 border-slate-200/80 bg-white">
            <div className="flex items-center justify-between text-xs font-semibold text-charcoal-muted">
              <span>Total Registered Users</span>
              <Users className="w-5 h-5 text-forest" />
            </div>
            <div className="text-2xl font-black text-charcoal mt-2">{stats?.total_users ?? users.length}</div>
            <div className="text-[11px] text-charcoal-muted mt-1">Platform authenticated accounts</div>
          </Card>

          <Card className="p-5 border-slate-200/80 bg-white">
            <div className="flex items-center justify-between text-xs font-semibold text-charcoal-muted">
              <span>Marketplace Properties</span>
              <Building className="w-5 h-5 text-forest" />
            </div>
            <div className="text-2xl font-black text-charcoal mt-2">{stats?.total_properties ?? properties.length}</div>
            <div className="text-[11px] text-charcoal-muted mt-1">Registered rental listings</div>
          </Card>

          <Card className="p-5 border-slate-200/80 bg-white">
            <div className="flex items-center justify-between text-xs font-semibold text-charcoal-muted">
              <span>Active Applications</span>
              <Clock className="w-5 h-5 text-amber-600" />
            </div>
            <div className="text-2xl font-black text-charcoal mt-2">{stats?.active_applications ?? 0}</div>
            <div className="text-[11px] text-charcoal-muted mt-1">In progress applications</div>
          </Card>

          <Card className="p-5 border-slate-200/80 bg-white">
            <div className="flex items-center justify-between text-xs font-semibold text-charcoal-muted">
              <span>Open Safety Reports</span>
              <AlertTriangle className="w-5 h-5 text-rose-500" />
            </div>
            <div className="text-2xl font-black text-charcoal mt-2">{stats?.open_moderation_reports ?? reports.length}</div>
            <div className="text-[11px] text-charcoal-muted mt-1">Pending investigator review</div>
          </Card>
        </div>
      )}

      {/* Tab 2: Moderation Queue */}
      {activeTab === "moderation" && (
        <div className="space-y-4">
          {reports.length === 0 ? (
            <Card className="p-12 text-center max-w-lg mx-auto border-slate-200/80">
              <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-charcoal">Moderation queue is clear</h3>
              <p className="text-xs text-charcoal-muted mt-1">No community reports pending investigation.</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {reports.map((r) => (
                <Card key={r.id} className="p-5 border-slate-200/80 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center space-x-2 mb-1">
                      <Badge variant={r.status === "pending" ? "warning" : "default"} className="capitalize">
                        {r.status}
                      </Badge>
                      <span className="text-xs font-bold text-charcoal uppercase">{r.reason.replace(/_/g, " ")}</span>
                      <span className="text-xs text-charcoal-muted">• Target: {r.target_type} ({r.target_id.slice(0, 8)}...)</span>
                    </div>
                    {r.description && <p className="text-xs text-charcoal mt-1 max-w-xl">{r.description}</p>}
                    <span className="text-[11px] text-charcoal-muted mt-1 block">Reported: {formatDate(r.created_at)}</span>
                  </div>

                  {r.status === "pending" && (
                    <div className="flex items-center space-x-2 self-end md:self-center">
                      <Button
                        size="sm"
                        variant="primary"
                        className="bg-forest hover:bg-forest-secondary gap-1"
                        onClick={() => handleResolveReport(r.id, "resolved")}
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Action & Resolve</span>
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1 text-charcoal-muted"
                        onClick={() => handleResolveReport(r.id, "dismissed")}
                      >
                        <X className="w-3.5 h-3.5" />
                        <span>Dismiss</span>
                      </Button>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Property Verification */}
      {activeTab === "properties" && (
        <div className="space-y-4">
          {properties.length === 0 ? (
            <EmptyState
              title="No properties in verification queue"
              description="All submitted properties have been reviewed."
            />
          ) : (
            <div className="space-y-3">
              {properties.map((p) => (
                <Card key={p.id} className="p-5 border-slate-200/80 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center space-x-2 mb-1">
                      <Badge variant={p.is_verified ? "forest" : "warning"}>
                        {p.is_verified ? "Verified" : "Pending Verification"}
                      </Badge>
                      <Badge variant="default">{p.configuration}</Badge>
                      <h4 className="font-bold text-charcoal text-sm">{p.title}</h4>
                    </div>
                    <p className="text-xs text-charcoal-muted flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-forest" />
                      <span>{p.address_display}, {p.city}</span>
                      <span className="mx-1">•</span>
                      <span className="font-semibold text-charcoal">{formatCurrency(p.monthly_rent, "INR")}/mo</span>
                    </p>
                  </div>

                  <div className="flex items-center space-x-2 self-end md:self-center">
                    {!p.is_verified && (
                      <Button
                        size="sm"
                        variant="primary"
                        className="gap-1 bg-forest hover:bg-forest-secondary"
                        onClick={() => handleApproveProperty(p.id)}
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Approve Verification</span>
                      </Button>
                    )}
                    <Link href={`/properties/${p.id}`}>
                      <Button size="sm" variant="ghost" className="gap-1">
                        <Eye className="w-3.5 h-3.5" />
                        <span>Inspect Listing</span>
                      </Button>
                    </Link>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Users */}
      {activeTab === "users" && (
        <Card className="p-0 border-slate-200/80 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-warm border-b border-slate-200 text-charcoal-muted font-semibold uppercase tracking-wider">
                <tr>
                  <th className="p-4">User</th>
                  <th className="p-4">Role</th>
                  <th className="p-4">Verified</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Registered</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-warm/50">
                    <td className="p-4">
                      <div className="font-bold text-charcoal">{u.full_name}</div>
                      <div className="text-[11px] text-charcoal-muted">{u.email}</div>
                    </td>
                    <td className="p-4">
                      <Badge variant="default" className="uppercase text-[10px]">
                        {u.role}
                      </Badge>
                    </td>
                    <td className="p-4">
                      {u.is_verified ? (
                        <span className="text-forest font-semibold flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Verified
                        </span>
                      ) : (
                        <span className="text-charcoal-muted">Unverified</span>
                      )}
                    </td>
                    <td className="p-4">
                      <Badge variant={u.is_active ? "success" : "danger"}>
                        {u.is_active ? "Active" : "Suspended"}
                      </Badge>
                    </td>
                    <td className="p-4 text-charcoal-muted">{formatDate(u.created_at)}</td>
                    <td className="p-4 text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        className={u.is_active ? "text-rose-600 border-rose-200 hover:bg-rose-50" : "text-forest border-forest hover:bg-forest-pale"}
                        onClick={() => handleToggleUserStatus(u.id, u.is_active)}
                      >
                        {u.is_active ? "Suspend" : "Activate"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
