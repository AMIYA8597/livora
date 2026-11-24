"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Button, Card, ErrorState, Tabs } from "@flatmate/ui";
import { Key, Lock, Shield, ShieldCheck, Sparkles, User } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { loginHref } from "@/lib/navigation";
import { trustSummary } from "@/lib/verification-model";
import { PageLoading } from "@/components/states/PageLoading";
import { InlineNotice } from "@/components/states/InlineNotice";
import { useMyProfileData } from "@/features/profile/useMyProfileData";
import {
  AccountSecurityPanel,
  DealbreakersPanel,
  LifestyleForm,
  PrivacySettingsForm,
  ProfileDetailsForm,
  VerificationForm,
} from "@/features/profile/components";
import { ProfileHeader } from "@/features/profile/components/ProfileHeader";

type ProfileTab = "profile" | "lifestyle" | "dealbreakers" | "privacy" | "verification" | "account";

const TABS = [
  { id: "profile", label: "Basic profile", icon: User },
  { id: "lifestyle", label: "Lifestyle", icon: Sparkles },
  { id: "dealbreakers", label: "Dealbreakers", icon: Shield },
  { id: "privacy", label: "Privacy", icon: Lock },
  { id: "verification", label: "Trust & verification", icon: ShieldCheck },
  { id: "account", label: "Account & security", icon: Key },
];

export default function ProfilePage() {
  const { user, isAuthenticated, isLoading: authLoading, refreshUser } = useAuth();
  const data = useMyProfileData(isAuthenticated);
  const [activeTab, setActiveTab] = useState<ProfileTab>("profile");
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const showNotice = (text: string, tone: "success" | "error" = "success") => {
    setNotice({ tone, text });
    setTimeout(() => setNotice(null), 4000);
  };

  if (authLoading) return <PageLoading />;

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto py-20 px-4 text-center">
        <Card className="p-8">
          <Lock className="w-10 h-10 text-forest mx-auto mb-3" />
          <h2 className="text-xl font-bold text-charcoal mb-2">Sign in required</h2>
          <p className="text-xs text-charcoal-muted mb-6">Sign in to view and edit your profile.</p>
          <Link href={loginHref("/profile")}>
            <Button variant="primary" className="w-full">Sign in</Button>
          </Link>
        </Card>
      </div>
    );
  }

  const profile = data.profile.data ?? null;
  const trust = data.trust.data ?? null;
  const firstLoad = data.profile.isLoading || data.lifestyle.isLoading || data.dealbreakers.isLoading || data.privacy.isLoading;
  const loadError = data.profile.error || data.lifestyle.error || data.dealbreakers.error || data.privacy.error;
  const retry = () => {
    data.profile.refetch();
    data.lifestyle.refetch();
    data.dealbreakers.refetch();
    data.privacy.refetch();
    data.trust.refetch();
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      <ProfileHeader
        user={user}
        profile={profile}
        trust={trust}
        onAvatarChanged={(p) => data.profile.setData(p)}
        onNotice={showNotice}
      />

      {notice && <InlineNotice tone={notice.tone}>{notice.text}</InlineNotice>}

      <Tabs tabs={TABS} activeTab={activeTab} onChange={(id) => setActiveTab(id as ProfileTab)} />

      <div role="tabpanel" id={`panel-${activeTab}`}>
        {firstLoad && activeTab !== "account" ? (
          <div className="max-w-2xl space-y-3" aria-busy="true">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-slate-100 rounded-2xl animate-pulse" />
            ))}
          </div>
        ) : loadError && activeTab !== "account" ? (
          <ErrorState title="Couldn't load your profile" message={loadError.message} onRetry={retry} />
        ) : (
          <>
            {activeTab === "profile" && (
              <ProfileDetailsForm
                key={profile?.id ?? "new"}
                initial={profile}
                onSaved={(p) => data.profile.setData(p)}
              />
            )}
            {activeTab === "lifestyle" && (
              <LifestyleForm
                key={data.lifestyle.data?.id ?? "new"}
                initial={data.lifestyle.data ?? null}
                onSaved={(l) => data.lifestyle.setData(l)}
              />
            )}
            {activeTab === "dealbreakers" && (
              <DealbreakersPanel
                items={data.dealbreakers.data ?? []}
                onAdded={(d) => data.dealbreakers.setData((prev = []) => [...prev, d])}
                onRemoved={(id) => data.dealbreakers.setData((prev = []) => prev.filter((d) => d.id !== id))}
              />
            )}
            {activeTab === "privacy" && (
              <PrivacySettingsForm
                key={data.privacy.data?.id ?? "new"}
                initial={data.privacy.data ?? null}
                onSaved={(p) => data.privacy.setData(p)}
              />
            )}
            {activeTab === "verification" && (
              <Card className="p-6 max-w-2xl">
                <div className="mb-6">
                  <h2 className="text-lg font-bold text-charcoal">Trust & verification</h2>
                  <p className="text-xs text-charcoal-muted mt-1">
                    Verify your mobile number (Account tab) and a work or college email. Verified members get more replies.
                  </p>
                </div>
                <div className="bg-forest-pale/60 border border-forest/20 rounded-xl p-4 mb-6 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <ShieldCheck className="w-8 h-8 text-forest shrink-0" />
                    <div>
                      <div className="text-xs font-bold text-forest">Status</div>
                      <div className="text-xs text-forest/80">
                        {trustSummary(trust?.badges, trust?.verifications)}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-charcoal-muted">Trust score</span>
                    <div className="text-xl font-bold text-forest">{trust?.total_trust_score ?? "—"}/100</div>
                  </div>
                </div>
                <VerificationForm trust={trust} onVerified={(s) => data.trust.setData(s)} />
              </Card>
            )}
            {activeTab === "account" && (
              <AccountSecurityPanel user={user} onUserChanged={refreshUser} onNotice={(m) => showNotice(m)} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
