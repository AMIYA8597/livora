import React from "react";
import Link from "next/link";
import { Sparkles, X } from "lucide-react";
import { pricingHref, type UpgradeHint } from "@/lib/billing-model";

interface UpgradePromptProps {
  hint: UpgradeHint;
  onDismiss?: () => void;
  className?: string;
  /** Open plans in a new tab, e.g. from a form whose unsaved input must survive. */
  newTab?: boolean;
}

/** Shown where a free-tier limit was hit: what happened, and a way to the plan that lifts it. */
export function UpgradePrompt({ hint, onDismiss, className = "", newTab = false }: UpgradePromptProps) {
  return (
    <div
      role="status"
      className={`p-3.5 border border-amber-200 bg-amber-50 text-amber-900 rounded-2xl text-sm flex items-start gap-3 ${className}`}
    >
      <Sparkles className="w-4 h-4 mt-0.5 shrink-0 text-amber-600" aria-hidden="true" />
      <div className="flex-1 min-w-0">
        <p>{hint.message}</p>
        <Link
          href={pricingHref(hint.plan)}
          {...(newTab ? { target: "_blank", rel: "noopener" } : {})}
          className="inline-flex items-center min-h-[44px] md:min-h-0 mt-1 font-semibold text-forest underline underline-offset-2"
        >
          {newTab ? "See plans (opens in a new tab)" : "See plans"}
        </Link>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] md:min-w-0 md:min-h-0 md:p-1 text-amber-700 hover:text-amber-900"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
