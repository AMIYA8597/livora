/**
 * Paid plans (Razorpay auto-renewing subscriptions).
 *
 * The API decides everything: what a plan costs, what it unlocks, and whether billing is on
 * (`/billing/plans` -> `enabled`). When a free limit is hit the API answers 402 with
 * `error_code: "UPGRADE_REQUIRED"` (or "FEATURED_LIMIT") plus `plan`/`feature`; `upgradeFrom`
 * turns that into something to show next to the action.
 */

export interface Plan {
  code: string;
  name: string;
  audience: "seeker" | "owner" | string;
  description?: string | null;
  price_inr: string | number;
  period: string;
  interval: number;
  features: Record<string, unknown>;
}

export interface PlansResponse {
  enabled: boolean;
  plans: Plan[];
}

export interface Entitlements {
  billing_enabled: boolean;
  who_liked_me: boolean;
  daily_likes: number | null;
  max_active_listings: number | null;
  featured_slots: number;
  plans: string[];
  paid_until?: string | null;
}

export interface MySubscription {
  id: string;
  plan_code: string;
  plan_name: string;
  status: string;
  expires_at?: string | null;
  cancel_at_period_end: boolean;
  is_live: boolean;
  renews: boolean;
  price_inr: string | number;
}

export interface BillingOverview {
  entitlements: Entitlements;
  usage: { likes_today: number; likes_reset_at: string; active_listings: number; featured_listings: number };
  subscriptions: MySubscription[];
}

export interface CheckoutSession {
  subscription_id: string;
  key_id: string;
  plan_code: string;
  plan_name: string;
  amount_inr: string | number;
  prefill: { name?: string; email?: string };
}

export interface UpgradeHint {
  message: string;
  plan: string;
  feature: string;
}

/** A 402 from the API, as something to show next to the action that hit the limit. */
export function upgradeFrom(err: unknown): UpgradeHint | null {
  // Duck-typed (ApiError from lib/api-client) so this module has no runtime imports.
  const e = err as { status?: unknown; detail?: unknown; raw?: unknown } | null;
  if (!e || typeof e !== "object" || e.status !== 402) return null;
  const raw = (e.raw ?? {}) as { plan?: unknown; feature?: unknown };
  return {
    message: (typeof e.detail === "string" && e.detail) || "This needs a paid plan.",
    plan: typeof raw.plan === "string" ? raw.plan : "",
    feature: typeof raw.feature === "string" ? raw.feature : "",
  };
}

export function pricingHref(plan?: string): string {
  return plan ? `/pricing?plan=${encodeURIComponent(plan)}` : "/pricing";
}

const PERIOD_LABEL: Record<string, [string, string]> = {
  daily: ["day", "days"],
  weekly: ["week", "weeks"],
  monthly: ["month", "months"],
  yearly: ["year", "years"],
};

/** "₹199 / month", "₹999 / 3 months". */
export function priceLabel(plan: Pick<Plan, "price_inr" | "period" | "interval">): string {
  const amount = Number(plan.price_inr);
  const rupees = Number.isFinite(amount)
    ? `₹${amount.toLocaleString("en-IN", { maximumFractionDigits: amount % 1 ? 2 : 0 })}`
    : "₹—";
  const [one, many] = PERIOD_LABEL[plan.period] ?? [plan.period, plan.period];
  return plan.interval > 1 ? `${rupees} / ${plan.interval} ${many}` : `${rupees} / ${one}`;
}

/** Plain-language list of what a plan unlocks, from its feature flags. */
export function planBenefits(features: Record<string, unknown>): string[] {
  const out: string[] = [];
  if (features.who_liked_me) out.push("See everyone who liked you");
  if ("daily_likes" in features) {
    out.push(features.daily_likes == null ? "Unlimited likes" : `${features.daily_likes} likes a day`);
  }
  if ("max_active_listings" in features) {
    out.push(
      features.max_active_listings == null
        ? "Publish as many listings as you like"
        : `Up to ${features.max_active_listings} published listings`,
    );
  }
  const slots = Number(features.featured_slots ?? 0);
  if (slots > 0) out.push(`Feature ${slots} listing${slots === 1 ? "" : "s"} at the top of search`);
  return out;
}

export function subscriptionLabel(sub: Pick<MySubscription, "status" | "renews" | "is_live" | "expires_at">, now = new Date()): string {
  const until = sub.expires_at ? new Date(sub.expires_at) : null;
  const date = until?.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  if (sub.status === "pending") return "Renewal payment failed. Razorpay will retry.";
  if (sub.status === "halted") return sub.is_live && date ? `Renewal failed. Active until ${date}.` : "Renewal failed.";
  if (sub.renews && date) return `Renews on ${date}`;
  if (sub.is_live && date && until && until > now) return `Active until ${date}. Won't renew.`;
  return "Ended";
}

