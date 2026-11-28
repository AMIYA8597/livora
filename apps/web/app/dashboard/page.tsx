"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ApplicationDTO, AppointmentDTO } from "@flatmate/contracts";
import { Avatar, Button, Card, ErrorState, Modal, Tabs } from "@flatmate/ui";
import { Calendar, FileText, Heart, LayoutDashboard, Shield, ShieldCheck, Sparkles, User } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useApiQuery } from "@/hooks/useApiQuery";
import { useSavedProperties } from "@/hooks/useSavedProperties";
import { apiClient } from "@/lib/api-client";
import { loginHref } from "@/lib/navigation";
import { trustSummary } from "@/lib/verification-model";
import { PageLoading } from "@/components/states/PageLoading";
import { InlineNotice } from "@/components/states/InlineNotice";
import { useMyProfileData } from "@/features/profile/useMyProfileData";
import { DealbreakersPanel, LifestyleForm, ProfileDetailsForm, VerificationForm } from "@/features/profile/components";
import { ApplicationsList } from "@/features/dashboard/components/ApplicationsList";
import { VisitsList } from "@/features/dashboard/components/VisitsList";
import { SavedPropertiesList } from "@/features/dashboard/components/SavedPropertiesList";

type DashboardTab = "applications" | "appointments" | "saved" | "profile" | "quiz" | "dealbreakers";

function ListSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-28 bg-slate-100 rounded-2xl animate-pulse" />
      ))}
    </div>
  );
}

function DashboardPageContent() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  // Notification links open a specific tab (e.g. ?tab=applications).
  const requestedTab = useSearchParams().get("tab");
  const [activeTab, setActiveTab] = useState<DashboardTab>(
    (["applications", "appointments", "saved", "profile", "quiz", "dealbreakers"] as const).includes(requestedTab as DashboardTab) ? (requestedTab as DashboardTab) : "applications",
  );
  const [isVerifyModalOpen, setIsVerifyModalOpen] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const showNotice = (text: string, tone: "success" | "error" = "success") => {
    setNotice({ tone, text });
    setTimeout(() => setNotice(null), 4000);
  };

  const applications = useApiQuery<ApplicationDTO[]>(isAuthenticated ? "/applications/me" : null);
  const appointments = useApiQuery<AppointmentDTO[]>(isAuthenticated ? "/appointments/" : null);
  const me = useMyProfileData(isAuthenticated);
  const saved = useSavedProperties();

  if (authLoading) return <PageLoading />;

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto py-20 px-4 text-center">
        <Card className="p-8">
          <LayoutDashboard className="w-12 h-12 text-forest mx-auto mb-3" />
          <h2 className="text-xl font-bold text-charcoal mb-2">Sign in to My Space</h2>
          <p className="text-xs text-charcoal-muted mb-6">Manage your applications, visits and saved homes.</p>
          <Link href={loginHref("/dashboard")}>
            <Button variant="primary" className="w-full">Sign in</Button>
          </Link>
        </Card>
      </div>
    );
  }

  const handleWithdraw = async (appId: string) => {
    // One tap can't be undone: the owner stops seeing the application.
    if (!confirm("Withdraw this application? The owner will no longer see it.")) return;
    setBusyId(appId);
    try {
      await apiClient(`/applications/${appId}/status`, { method: "PATCH", body: JSON.stringify({ status: "withdrawn" }) });
      applications.setData((prev = []) => prev.map((a) => (a.id === appId ? { ...a, status: "withdrawn" } : a)));
      showNotice("Application withdrawn.");
    } catch (err) {
      showNotice(err instanceof Error ? err.message : "Failed to withdraw application", "error");
    } finally {
      setBusyId(null);
    }
  };

  const handleCancelVisit = async (aptId: string) => {
    if (!confirm("Cancel this visit? The host will be told.")) return;
    setBusyId(aptId);
    try {
      await apiClient(`/appointments/${aptId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "cancelled", cancellation_reason: "Cancelled by applicant" }),
      });
      appointments.setData((prev = []) => prev.map((a) => (a.id === aptId ? { ...a, status: "cancelled" } : a)));
      showNotice("Visit cancelled.");
    } catch (err) {
      showNotice(err instanceof Error ? err.message : "Failed to cancel visit", "error");
    } finally {
      setBusyId(null);
    }
  };

  const trust = me.trust.data ?? null;
  const tabs = [
    { id: "applications", label: `Applications (${applications.data?.length ?? 0})`, icon: FileText },
    { id: "appointments", label: `Visits (${appointments.data?.length ?? 0})`, icon: Calendar },
    { id: "saved", label: `Saved (${saved.ids.length})`, icon: Heart },
    { id: "profile", label: "Profile", icon: User },
    { id: "quiz", label: "Lifestyle", icon: Sparkles },
    { id: "dealbreakers", label: `Dealbreakers (${me.dealbreakers.data?.length ?? 0})`, icon: Shield },
  ];

  const renderList = <T,>(
    q: { data: T[] | undefined; isLoading: boolean; error: Error | null; refetch: () => void },
    title: string,
    render: (items: T[]) => React.ReactNode,
  ) =>
    q.isLoading ? <ListSkeleton /> : q.error ? <ErrorState title={title} message={q.error.message} onRetry={q.refetch} /> : render(q.data ?? []);

  const profileTabState = (q: { isLoading: boolean; error: Error | null; refetch: () => void }, node: () => React.ReactNode) =>
    q.isLoading ? <ListSkeleton /> : q.error ? <ErrorState message={q.error.message} onRetry={q.refetch} /> : node();

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <Avatar alt={user?.full_name || "User"} size="lg" isVerified={user?.is_verified} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold text-charcoal break-words">{user?.full_name}</h1>
              <span className="text-xs uppercase font-bold text-forest bg-forest-pale px-2.5 py-0.5 rounded-full">{user?.role}</span>
            </div>
            <p className="text-xs text-charcoal-muted mt-0.5 break-all">{user?.email}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 bg-forest-pale/60 border border-forest/20 px-4 py-2.5 rounded-2xl text-forest text-xs">
          <ShieldCheck className="w-5 h-5 text-forest shrink-0" />
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold">Trust score: {trust?.total_trust_score ?? "—"}/100</span>
              {!trust?.is_fully_verified && !(trust?.verifications?.length) && (
                <button
                  type="button"
                  onClick={() => setIsVerifyModalOpen(true)}
                  className="min-h-[44px] text-[11px] font-semibold text-forest underline hover:text-forest-light"
                >
                  Get verified
                </button>
              )}
            </div>
            <span className="text-forest/80 text-[11px]">
              {trustSummary(trust?.badges, trust?.verifications)}
            </span>
          </div>
        </div>
      </div>

      {notice && <InlineNotice tone={notice.tone}>{notice.text}</InlineNotice>}

      <Tabs tabs={tabs} activeTab={activeTab} onChange={(id) => setActiveTab(id as DashboardTab)} />

      <div role="tabpanel" id={`panel-${activeTab}`}>
        {activeTab === "applications" &&
          renderList(applications, "Couldn't load your applications", (items) => (
            <ApplicationsList items={items} onWithdraw={handleWithdraw} busyId={busyId} />
          ))}
        {activeTab === "appointments" &&
          renderList(appointments, "Couldn't load your visits", (items) => (
            <VisitsList items={items} onCancel={handleCancelVisit} busyId={busyId} />
          ))}
        {activeTab === "saved" && <SavedPropertiesList onRemoved={() => showNotice("Removed from saved.")} />}
        {activeTab === "profile" &&
          profileTabState(me.profile, () => (
            <ProfileDetailsForm
              initial={me.profile.data ?? null}
              onSaved={(p) => me.profile.setData(p)}
            />
          ))}
        {activeTab === "quiz" &&
          profileTabState(me.lifestyle, () => (
            <LifestyleForm
              initial={me.lifestyle.data ?? null}
              onSaved={(l) => me.lifestyle.setData(l)}
            />
          ))}
        {activeTab === "dealbreakers" &&
          profileTabState(me.dealbreakers, () => (
            <DealbreakersPanel
              items={me.dealbreakers.data ?? []}
              onAdded={(d) => me.dealbreakers.setData((prev = []) => [...prev, d])}
              onRemoved={(id) => me.dealbreakers.setData((prev = []) => prev.filter((d) => d.id !== id))}
            />
          ))}
      </div>

      <Modal
        isOpen={isVerifyModalOpen}
        onClose={() => setIsVerifyModalOpen(false)}
        title="Verify your work or college email"
        description="A verified badge shows people where you work or study, and gets more replies."
      >
        <div className="mt-2">
          <VerificationForm trust={me.trust.data} onVerified={(s) => me.trust.setData(s)} />
        </div>
      </Modal>
    </div>
  );
}

export default function DashboardPage() {
  // useSearchParams needs a Suspense boundary so the rest of the route can prerender.
  return (
    <Suspense fallback={<PageLoading />}>
      <DashboardPageContent />
    </Suspense>
  );
}
