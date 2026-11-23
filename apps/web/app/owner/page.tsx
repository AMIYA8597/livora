"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button, Card, EmptyState, ErrorState, Tabs } from "@flatmate/ui";
import { Building, Calendar, FileText, Plus } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useApiQuery } from "@/hooks/useApiQuery";
import { apiClient } from "@/lib/api-client";
import { loginHref } from "@/lib/navigation";
import { PageLoading } from "@/components/states/PageLoading";
import { InlineNotice } from "@/components/states/InlineNotice";
import { OwnerStats, buildOwnerStats } from "@/features/owner/components/OwnerStats";
import { OwnerPropertiesList } from "@/features/owner/components/OwnerPropertiesList";
import { OwnerApplicationsList } from "@/features/owner/components/OwnerApplicationsList";
import { OwnerVisitsList } from "@/features/owner/components/OwnerVisitsList";
import {
  normalizeApplication,
  type OwnerApplicantCard,
  type OwnerAppointment,
  type OwnerProperty,
  type OwnerStatsData,
} from "@/features/owner/types";

type OwnerTab = "properties" | "applications" | "appointments";
type Notice = { tone: "success" | "error"; text: string } | null;

const OPEN_APPLICATION = new Set(["submitted", "reviewing", "pending"]);

function ListSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true">
      {[1, 2].map((i) => (
        <div key={i} className="h-28 bg-slate-100 rounded-2xl animate-pulse" />
      ))}
    </div>
  );
}

export default function OwnerPortalPage() {
  const { isAuthenticated, isLoading: authLoading, isOwner } = useAuth();
  const router = useRouter();
  const canView = isAuthenticated && isOwner;
  const [activeTab, setActiveTab] = useState<OwnerTab>("properties");
  const [notice, setNotice] = useState<Notice>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const statsQuery = useApiQuery<OwnerStatsData>(canView ? "/owners/dashboard" : null);
  const propertiesQuery = useApiQuery<OwnerProperty[]>(canView ? "/owners/properties" : null);
  const applicationsQuery = useApiQuery<OwnerApplicantCard[]>(canView ? "/owners/applications" : null);
  const appointmentsQuery = useApiQuery<OwnerAppointment[]>(canView ? "/appointments" : null);

  const properties = useMemo(() => propertiesQuery.data ?? [], [propertiesQuery.data]);
  const applications = useMemo(() => (applicationsQuery.data ?? []).map(normalizeApplication), [applicationsQuery.data]);
  const appointments = useMemo(() => appointmentsQuery.data ?? [], [appointmentsQuery.data]);
  const stats = statsQuery.data;

  /** Run one owner action: one busy row at a time, errors shown inline instead of alert(). */
  const act = async (id: string, run: () => Promise<void>, success: string) => {
    setBusyId(id);
    setNotice(null);
    try {
      await run();
      setNotice({ tone: "success", text: success });
    } catch (err) {
      setNotice({ tone: "error", text: err instanceof Error ? err.message : "Something went wrong" });
    } finally {
      setBusyId(null);
    }
  };

  const toggleListing = (prop: OwnerProperty) => {
    const live = prop.listing_status === "published" || (!prop.listing_status && prop.is_active);
    const next = live ? "paused" : "published";
    return act(
      prop.id,
      async () => {
        await apiClient(`/properties/${prop.id}/status`, { method: "PATCH", body: JSON.stringify({ listing_status: next }) });
        propertiesQuery.setData((prev = []) =>
          prev.map((p) => (p.id === prop.id ? { ...p, listing_status: next, is_active: next === "published" } : p)),
        );
        statsQuery.refetch();
      },
      next === "published" ? "Listing is live in search." : "Listing paused. It no longer shows in search.",
    );
  };

  const vacateBed = (bedId: string) =>
    act(
      bedId,
      async () => {
        await apiClient(`/properties/beds/${bedId}/vacate`, { method: "POST" });
        propertiesQuery.refetch();
        statsQuery.refetch();
      },
      "Bed marked as vacant.",
    );

  const decideApplication = (id: string, status: "accepted" | "rejected") =>
    act(
      id,
      async () => {
        await apiClient(`/applications/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
        applicationsQuery.refetch();
        statsQuery.refetch();
      },
      status === "accepted" ? "Application accepted. The applicant has been notified." : "Application declined.",
    );

  const decideVisit = (id: string, status: "confirmed" | "cancelled") =>
    act(
      id,
      async () => {
        await apiClient(`/appointments/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
        appointmentsQuery.setData((prev = []) => prev.map((a) => (a.id === id ? { ...a, status } : a)));
      },
      status === "confirmed" ? "Visit confirmed." : "Visit declined.",
    );

  if (authLoading) return <PageLoading />;

  if (!isAuthenticated || !isOwner) {
    return (
      <div className="max-w-md mx-auto py-16 sm:py-20 px-4 text-center">
        <Card className="p-6 sm:p-8">
          <Building className="w-12 h-12 text-forest mx-auto mb-3" />
          <h1 className="text-xl font-bold text-charcoal mb-2">Owner portal</h1>
          <p className="text-sm text-charcoal-muted mb-6">
            {isAuthenticated
              ? "This area is for property owners. Your account doesn't have the owner role."
              : "Sign in with an owner account to manage your listings, applications and visits."}
          </p>
          {isAuthenticated ? (
            <Link href="/properties">
              <Button variant="primary" className="w-full">Browse listings</Button>
            </Link>
          ) : (
            <Link href={loginHref("/owner")}>
              <Button variant="primary" className="w-full">Sign in</Button>
            </Link>
          )}
        </Card>
      </div>
    );
  }

  const isLoading = statsQuery.isLoading || propertiesQuery.isLoading || applicationsQuery.isLoading || appointmentsQuery.isLoading;
  const loadError = statsQuery.error || propertiesQuery.error || applicationsQuery.error || appointmentsQuery.error;
  const reloadAll = () => {
    statsQuery.refetch();
    propertiesQuery.refetch();
    applicationsQuery.refetch();
    appointmentsQuery.refetch();
  };
  const pendingApplications = applications.filter((a) => OPEN_APPLICATION.has(a.status)).length;

  const tabs = [
    { id: "properties", label: `Properties (${properties.length})`, icon: Building },
    { id: "applications", label: `Applications (${pendingApplications})`, icon: FileText },
    { id: "appointments", label: `Visits (${appointments.length})`, icon: Calendar },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-10 space-y-6 sm:space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-charcoal tracking-tight">Owner portal</h1>
          <p className="text-charcoal-muted text-sm mt-1">Your listings, rooms, applications and viewing requests.</p>
        </div>
        <Link href="/owner/listings/create" className="sm:shrink-0">
          <Button variant="primary" className="gap-2 w-full sm:w-auto">
            <Plus className="w-4 h-4" />
            <span>List a property</span>
          </Button>
        </Link>
      </div>

      {loadError && !isLoading && (
        <ErrorState title="Some of your data didn't load" message={loadError.message} onRetry={reloadAll} />
      )}
      {notice && <InlineNotice tone={notice.tone}>{notice.text}</InlineNotice>}

      <OwnerStats
        stats={buildOwnerStats({
          totalProperties: stats?.total_properties ?? properties.length,
          activeListings: stats?.active_listings ?? properties.filter((p) => p.is_active).length,
          pendingApplications: stats?.pending_applications ?? pendingApplications,
          visits: appointments.length,
          revenue: Number(stats?.estimated_monthly_revenue ?? 0),
        })}
      />

      <Tabs tabs={tabs} activeTab={activeTab} onChange={(id) => setActiveTab(id as OwnerTab)} />

      <div role="tabpanel" id={`panel-${activeTab}`}>
        {isLoading ? (
          <ListSkeleton />
        ) : activeTab === "properties" ? (
          properties.length === 0 ? (
            <EmptyState
              title="No properties yet"
              description="List a flat, room or PG to start receiving applications from verified seekers."
              actionLabel="List a property"
              onAction={() => router.push("/owner/listings/create")}
            />
          ) : (
            <OwnerPropertiesList properties={properties} busyId={busyId} onToggleStatus={toggleListing} onVacateBed={vacateBed} />
          )
        ) : activeTab === "applications" ? (
          applications.length === 0 ? (
            <EmptyState
              title="No applications yet"
              description="When seekers apply for your listings, their introduction and offer appear here."
            />
          ) : (
            <OwnerApplicationsList items={applications} busyId={busyId} onDecide={decideApplication} />
          )
        ) : appointments.length === 0 ? (
          <EmptyState title="No viewing requests" description="Visit requests from seekers appear here for you to confirm." />
        ) : (
          <OwnerVisitsList items={appointments} busyId={busyId} onDecide={decideVisit} />
        )}
      </div>
    </div>
  );
}
