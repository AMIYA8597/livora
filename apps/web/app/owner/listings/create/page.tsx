"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Button, Card } from "@flatmate/ui";
import { ArrowLeft, ArrowRight, Building, CheckCircle2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { loginHref } from "@/lib/navigation";
import { localDateInputValue } from "@/lib/utils";
import { PageLoading } from "@/components/states/PageLoading";
import { InlineNotice } from "@/components/states/InlineNotice";
import { UpgradePrompt } from "@/components/billing/UpgradePrompt";
import { upgradeFrom, type UpgradeHint } from "@/lib/billing-model";
import { WIZARD_STEPS, buildListingPayload, firstInvalidStep, initialDraft, validateStep, type ListingDraft } from "@/features/listings/draft";
import type { StepProps } from "@/features/listings/components/fields";
import { BasicsStep, LayoutStep, LocationStep } from "@/features/listings/components/DetailsSteps";
import { BedsStep, RoomsStep } from "@/features/listings/components/InventorySteps";
import { AmenitiesStep, PricingStep } from "@/features/listings/components/TermsSteps";
import { PhotosStep, ReviewStep } from "@/features/listings/components/PublishSteps";

const STEP_COMPONENTS: React.ComponentType<StepProps>[] = [
  BasicsStep,
  LocationStep,
  LayoutStep,
  RoomsStep,
  BedsStep,
  PricingStep,
  AmenitiesStep,
  PhotosStep,
  ReviewStep,
];

export default function ListingWizardPage() {
  const { isAuthenticated, isLoading: authLoading, canList } = useAuth();
  const [draft, setDraft] = useState<ListingDraft>(initialDraft);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [upgrade, setUpgrade] = useState<UpgradeHint | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [publishedId, setPublishedId] = useState<string | null>(null);

  const update = (patch: Partial<ListingDraft>) => {
    setDraft((d) => ({ ...d, ...patch }));
    setError(null);
  };

  const goTo = (target: number) => {
    setError(null);
    setStep(target);
    window.scrollTo({ top: 0 });
  };

  const next = () => {
    const problem = validateStep(step, draft);
    if (problem) {
      setError(problem);
      return;
    }
    goTo(step + 1);
  };

  const publish = async () => {
    const invalid = firstInvalidStep(draft);
    if (invalid) {
      goTo(invalid.step);
      setError(invalid.message);
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setUpgrade(null);
    try {
      const res = await apiClient<{ id: string }>("/properties", {
        method: "POST",
        body: JSON.stringify(buildListingPayload(draft, localDateInputValue())),
      });
      setPublishedId(res.id);
    } catch (err) {
      const hint = upgradeFrom(err);
      if (hint) setUpgrade({ ...hint, message: `${hint.message} Your listing stays here: publish again once you're ready.` });
      else setError(err instanceof Error ? err.message : "Couldn't publish the listing");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authLoading) return <PageLoading />;

  if (!isAuthenticated || !canList) {
    return (
      <div className="max-w-md mx-auto py-16 px-4 text-center">
        <Card className="p-6 sm:p-8">
          <Building className="w-12 h-12 text-forest mx-auto mb-3" />
          <h1 className="text-xl font-bold text-charcoal mb-2">List a property</h1>
          <p className="text-sm text-charcoal-muted mb-6">
            {isAuthenticated
              ? "Listing needs an owner, PG operator or verified broker account. Brokers can ask for access from their profile."
              : "Sign in to list a property."}
          </p>
          <Link href={isAuthenticated ? "/properties" : loginHref("/owner/listings/create")}>
            <Button variant="primary" className="w-full">{isAuthenticated ? "Browse listings" : "Sign in"}</Button>
          </Link>
        </Card>
      </div>
    );
  }

  if (publishedId) {
    return (
      <div className="max-w-2xl mx-auto py-16 px-4 text-center space-y-5">
        <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-3xl flex items-center justify-center mx-auto">
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-extrabold text-charcoal">Your listing is live</h1>
        <p className="text-sm text-charcoal-muted max-w-md mx-auto">Seekers can now find it in search and apply.</p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-4">
          <Link href={`/properties/${publishedId}`} className="w-full sm:w-auto">
            <Button variant="primary" className="w-full">View listing</Button>
          </Link>
          <Link href="/owner" className="w-full sm:w-auto">
            <Button variant="outline" className="w-full">Back to owner portal</Button>
          </Link>
        </div>
      </div>
    );
  }

  const StepComponent = STEP_COMPONENTS[step];
  const isLast = step === WIZARD_STEPS.length - 1;

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 sm:py-10 space-y-6">
      <div className="flex items-start justify-between gap-3 border-b border-slate-200 pb-4">
        <div className="min-w-0">
          <span className="text-xs font-semibold text-forest uppercase tracking-wider block">
            Step {step + 1} of {WIZARD_STEPS.length}
          </span>
          <h1 className="text-xl sm:text-2xl font-extrabold text-charcoal">{WIZARD_STEPS[step]}</h1>
        </div>
        <Link href="/owner" className="inline-flex items-center min-h-[44px] text-xs font-semibold text-charcoal-muted hover:text-charcoal shrink-0">
          Cancel
        </Link>
      </div>

      <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden" role="progressbar" aria-valuemin={1} aria-valuemax={WIZARD_STEPS.length} aria-valuenow={step + 1}>
        <div className="h-full bg-forest transition-all" style={{ width: `${((step + 1) / WIZARD_STEPS.length) * 100}%` }} />
      </div>

      {error && <InlineNotice tone="error">{error}</InlineNotice>}
      {upgrade && <UpgradePrompt hint={upgrade} newTab onDismiss={() => setUpgrade(null)} />}

      <Card className="p-4 sm:p-6 border-slate-200/80 shadow-xs">
        <StepComponent draft={draft} update={update} />
      </Card>

      <div className="flex items-center justify-between gap-3">
        <Button variant="outline" disabled={step === 0 || isSubmitting} onClick={() => goTo(step - 1)} className="gap-2">
          <ArrowLeft className="w-4 h-4" />
          <span>Back</span>
        </Button>
        {isLast ? (
          <Button variant="primary" isLoading={isSubmitting} onClick={publish} className="gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>Publish listing</span>
          </Button>
        ) : (
          <Button variant="primary" onClick={next} className="gap-2">
            <span>Continue</span>
            <ArrowRight className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
