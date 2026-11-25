"use client";

import React, { useState } from "react";
import type { UserDTO } from "@flatmate/contracts";
import { Button, Card } from "@flatmate/ui";
import { Copy, Fingerprint, Mail, Shield } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useAppFeatures } from "@/lib/app-features";
import { InlineNotice } from "@/components/states/InlineNotice";
import { PhoneVerification } from "./PhoneVerification";
import { BlockedUsersCard } from "./BlockedUsersCard";
import { DataControlsCard } from "./DataControlsCard";

interface AccountSecurityPanelProps {
  user: UserDTO | null;
  onUserChanged: () => Promise<void> | void;
  onNotice: (message: string) => void;
}

export function AccountSecurityPanel({ user, onUserChanged, onNotice }: AccountSecurityPanelProps) {
  const features = useAppFeatures();
  const [resetNotice, setResetNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [isRequestingReset, setIsRequestingReset] = useState(false);

  const handleRequestPasswordReset = async () => {
    if (!user?.email) return;
    setIsRequestingReset(true);
    try {
      await apiClient("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email: user.email }) });
      setResetNotice({ tone: "success", text: "We've emailed you a link to reset your password." });
    } catch (err) {
      setResetNotice({ tone: "error", text: err instanceof Error ? err.message : "Failed to request password reset" });
    } finally {
      setIsRequestingReset(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <Card className="p-6">
        <h2 className="text-lg font-bold text-charcoal mb-1">Account & identity</h2>
        <p className="text-xs text-charcoal-muted mb-4">Sign-in details and contact verification.</p>

        <div className="space-y-3 text-xs">
          {user?.id && (
            <div className="flex items-center justify-between gap-2 p-3 bg-warm rounded-xl border border-slate-200/60">
              <div className="flex items-center gap-2 min-w-0">
                <Fingerprint className="w-4 h-4 text-forest shrink-0" />
                <div className="min-w-0">
                  <span className="font-mono text-[11px] text-charcoal block break-all">{user.id}</span>
                  <span className="text-[10px] text-charcoal-muted">Your user ID: share it so a group can add you</span>
                </div>
              </div>
              <Button
                size="sm"
                variant="ghost"
                className="gap-1 shrink-0"
                onClick={() =>
                  navigator.clipboard
                    .writeText(user.id)
                    .then(() => onNotice("User ID copied."))
                    .catch(() => onNotice("Couldn't copy. Select the ID and copy it manually."))
                }
              >
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </Button>
            </div>
          )}
          <div className="flex items-center justify-between gap-2 p-3 bg-warm rounded-xl border border-slate-200/60">
            <div className="flex items-center gap-2 min-w-0">
              <Mail className="w-4 h-4 text-forest shrink-0" />
              <div className="min-w-0">
                <span className="font-semibold text-charcoal block truncate">{user?.email}</span>
                <span className="text-[10px] text-charcoal-muted">Primary account login</span>
              </div>
            </div>
          </div>

          {features?.phone_verification && (
            <PhoneVerification user={user} onVerified={onUserChanged} onNotice={onNotice} />
          )}

          <div className="p-4 bg-warm rounded-xl border border-slate-200/60 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="font-semibold text-charcoal block">Password</span>
                <span className="text-[10px] text-charcoal-muted">Get a secure reset link by email.</span>
              </div>
              <Button size="sm" variant="outline" onClick={handleRequestPasswordReset} isLoading={isRequestingReset} className="min-h-[44px]">
                Reset password
              </Button>
            </div>
            {resetNotice && <InlineNotice tone={resetNotice.tone}>{resetNotice.text}</InlineNotice>}
          </div>
        </div>
      </Card>

      <BlockedUsersCard />

      <DataControlsCard />

      <Card className="p-6 border-forest/20 bg-forest-pale/20">
        <div className="flex items-center gap-2 mb-2">
          <Shield className="w-5 h-5 text-forest" />
          <h3 className="text-sm font-bold text-charcoal">Your data rights (DPDP Act 2023)</h3>
        </div>
        <p className="text-xs text-charcoal-muted leading-relaxed">
          Under India&apos;s Digital Personal Data Protection Act you can ask for a summary of your personal
          data, its correction, or its erasure.
        </p>
        <div className="mt-3 pt-3 border-t border-forest/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
          <span className="text-charcoal-muted">To correct your data, or for any other request about it:</span>
          <a
            href="mailto:privacy@flatmate.platform?subject=DPDP%20Data%20Erasure%20Request"
            className="font-bold text-forest hover:underline min-h-[44px] inline-flex items-center"
          >
            Contact our Data Protection Officer →
          </a>
        </div>
      </Card>
    </div>
  );
}
