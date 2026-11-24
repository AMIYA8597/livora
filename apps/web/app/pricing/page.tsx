"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Badge, Button, Card, Skeleton } from "@flatmate/ui";
import { Check, Home, Search, ShieldCheck } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useApiQuery } from "@/hooks/useApiQuery";
import { InlineNotice } from "@/components/states/InlineNotice";
import { loginHref } from "@/lib/navigation";
import {
  cancelSubscription,
  planBenefits,
  priceLabel,
  subscribeToPlan,
  subscriptionLabel,
  type BillingOverview,
  type Plan,
  type PlansResponse,
} from "@/lib/billing";

type Notice = { tone: "success" | "error"; text: string } | null;

const AUDIENCE: Record<string, { title: string; icon: typeof Search }> = {
  seeker: { title: "For people looking for a place", icon: Search },
  owner: { title: "For owners and hosts", icon: Home },
};

function PricingContent() {
  const { isAuthenticated } = useAuth();
  const highlighted = useSearchParams().get("plan");
  const plansQuery = useApiQuery<PlansResponse>("/billing/plans");
  const meQuery = useApiQuery<BillingOverview>(isAuthenticated ? "/billing/me" : null);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmCancel, setConfirmCancel] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);

  const enabled = plansQuery.data?.enabled ?? false;
  const plans = plansQuery.data?.plans ?? [];
  const subs = meQuery.data?.subscriptions ?? [];
  const liveSub = (code: string) => subs.find((s) => s.plan_code === code && s.is_live);

  const subscribe = async (plan: Plan) => {
    setBusy(plan.code);
    setNotice(null);
    try {
      const outcome = await subscribeToPlan(plan.code);
      if (outcome.status === "paid") {
        setNotice({ tone: "success", text: `You're on ${plan.name}. Your new features are ready.` });
        meQuery.refetch();
      } else if (outcome.status === "failed") {
        setNotice({ tone: "error", text: outcome.message });
        meQuery.refetch();
      }
    } catch (err) {
      setNotice({ tone: "error", text: err instanceof Error ? err.message : "Couldn't start the payment." });
    } finally {
      setBusy(null);
    }
  };

  const cancel = async (subId: string, planName: string) => {
    setBusy(subId);
    setNotice(null);
    try {
      await cancelSubscription(subId);
      setNotice({ tone: "success", text: `${planName} won't renew. You keep it until the paid period ends.` });
      meQuery.refetch();
    } catch (err) {
      setNotice({ tone: "error", text: err instanceof Error ? err.message : "Couldn't cancel." });
    } finally {
      setBusy(null);
      setConfirmCancel(null);
    }
  };

  const audiences = Array.from(new Set(plans.map((p) => p.audience)));

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      <div className="max-w-2xl">
        <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">Plans</h1>
        <p className="text-charcoal-muted text-sm mt-2 leading-relaxed">
          Searching, messaging, applying and booking visits are free. Plans add a few extras and renew monthly
          until you cancel. You keep a cancelled plan until the end of the month you paid for.
        </p>
      </div>

      {notice && <InlineNotice tone={notice.tone}>{notice.text}</InlineNotice>}
      {plansQuery.data && !enabled && (
        <InlineNotice tone="success">Paid plans aren&apos;t available yet. Everything is free for now.</InlineNotice>
      )}
      {plansQuery.error && <InlineNotice tone="error">Couldn&apos;t load plans. Please try again.</InlineNotice>}

      {plansQuery.isLoading ? (
        <div className="grid gap-6 md:grid-cols-2">
          <Skeleton variant="card" height={280} />
          <Skeleton variant="card" height={280} />
        </div>
      ) : (
        audiences.map((audience) => {
          const meta = AUDIENCE[audience] ?? { title: "Plans", icon: Search };
          const Icon = meta.icon;
          return (
            <section key={audience} aria-labelledby={`plans-${audience}`} className="space-y-4">
              <h2 id={`plans-${audience}`} className="text-lg font-bold text-charcoal flex items-center gap-2">
                <Icon className="w-5 h-5 text-forest" aria-hidden="true" />
                {meta.title}
              </h2>
              <div className="grid gap-6 md:grid-cols-2">
                {plans.filter((p) => p.audience === audience).map((plan) => {
                  const mine = liveSub(plan.code);
                  return (
                    <Card
                      key={plan.code}
                      className={`p-6 bg-white flex flex-col gap-4 ${
                        highlighted === plan.code ? "border-forest ring-2 ring-forest/30" : "border-warm-200"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-xl font-bold text-charcoal">{plan.name}</h3>
                          {plan.description && <p className="text-sm text-charcoal-muted mt-1">{plan.description}</p>}
                        </div>
                        {mine && <Badge variant="forest" className="whitespace-nowrap shrink-0">Your plan</Badge>}
                      </div>
                      <p className="text-2xl font-extrabold text-charcoal">{priceLabel(plan)}</p>
                      <ul className="space-y-2 text-sm text-charcoal">
                        {planBenefits(plan.features).map((b) => (
                          <li key={b} className="flex items-start gap-2">
                            <Check className="w-4 h-4 mt-0.5 text-forest shrink-0" aria-hidden="true" />
                            <span>{b}</span>
                          </li>
                        ))}
                      </ul>

                      <div className="mt-auto pt-2 space-y-2">
                        {mine ? (
                          <>
                            <p className="text-xs text-charcoal-muted">{subscriptionLabel(mine)}</p>
                            {mine.renews &&
                              (confirmCancel === mine.id ? (
                                <div className="flex flex-wrap gap-2">
                                  <Button
                                    variant="danger"
                                    size="sm"
                                    isLoading={busy === mine.id}
                                    onClick={() => cancel(mine.id, plan.name)}
                                  >
                                    Yes, stop renewing
                                  </Button>
                                  <Button variant="ghost" size="sm" onClick={() => setConfirmCancel(null)}>
                                    Keep my plan
                                  </Button>
                                </div>
                              ) : (
                                <Button variant="outline" size="sm" onClick={() => setConfirmCancel(mine.id)}>
                                  Cancel renewal
                                </Button>
                              ))}
                          </>
                        ) : !enabled ? (
                          <Button variant="primary" className="w-full min-h-[44px]" disabled>
                            Coming soon
                          </Button>
                        ) : !isAuthenticated ? (
                          <Link href={loginHref(`/pricing?plan=${plan.code}`)}>
                            <Button variant="primary" className="w-full min-h-[44px]">Sign in to subscribe</Button>
                          </Link>
                        ) : (
                          <Button
                            variant="primary"
                            className="w-full min-h-[44px]"
                            disabled={busy !== null}
                            isLoading={busy === plan.code}
                            onClick={() => subscribe(plan)}
                          >
                            {`Get ${plan.name}`}
                          </Button>
                        )}
                      </div>
                    </Card>
                  );
                })}
              </div>
            </section>
          );
        })
      )}

      <p className="text-xs text-charcoal-muted flex items-start gap-2 max-w-2xl">
        <ShieldCheck className="w-4 h-4 text-forest shrink-0" aria-hidden="true" />
        <span>
          Payments are processed by Razorpay (UPI Autopay, cards and more). Flatmate never sees your card or UPI PIN.
        </span>
      </p>
    </div>
  );
}

export default function PricingPage() {
  return (
    <Suspense fallback={<div className="max-w-5xl mx-auto px-4 py-10"><Skeleton variant="card" height={280} /></div>}>
      <PricingContent />
    </Suspense>
  );
}
