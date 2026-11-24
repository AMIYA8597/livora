/** Razorpay Checkout for paid plans. Pure helpers and types live in ./billing-model. */
import { apiClient } from "./api-client";
import type { CheckoutSession } from "./billing-model";

export * from "./billing-model";

// ------------------------------------------------------------------------------ checkout

interface RazorpayHandlerResponse {
  razorpay_payment_id: string;
  razorpay_subscription_id: string;
  razorpay_signature: string;
}

interface RazorpayInstance {
  open(): void;
  on(event: "payment.failed", cb: (resp: { error?: { description?: string } }) => void): void;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}

const CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";
let scriptPromise: Promise<void> | null = null;

function loadCheckoutScript(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("Checkout needs a browser"));
  if (window.Razorpay) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = CHECKOUT_SRC;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => {
        scriptPromise = null;
        reject(new Error("Couldn't load the payment window. Check your connection and try again."));
      };
      document.body.appendChild(script);
    });
  }
  return scriptPromise;
}

export type CheckoutOutcome = { status: "paid" } | { status: "dismissed" } | { status: "failed"; message: string };

/**
 * Start a subscription: the API creates it at Razorpay, Razorpay Checkout collects the payment
 * mandate (UPI Autopay, card, ...), and the API verifies the result before anything unlocks.
 */
export async function subscribeToPlan(planCode: string): Promise<CheckoutOutcome> {
  const session = await apiClient<CheckoutSession>("/billing/subscriptions", {
    method: "POST",
    body: JSON.stringify({ plan_code: planCode }),
  });
  await loadCheckoutScript();
  const Razorpay = window.Razorpay;
  if (!Razorpay) throw new Error("Couldn't load the payment window.");

  return new Promise<CheckoutOutcome>((resolve) => {
    let settled = false;
    const finish = (outcome: CheckoutOutcome) => {
      if (!settled) {
        settled = true;
        resolve(outcome);
      }
    };
    const rzp = new Razorpay({
      key: session.key_id,
      subscription_id: session.subscription_id,
      name: "Flatmate",
      description: session.plan_name,
      prefill: session.prefill,
      theme: { color: "#1f5f45" },
      handler: async (resp: RazorpayHandlerResponse) => {
        try {
          await apiClient("/billing/subscriptions/verify", { method: "POST", body: JSON.stringify(resp) });
          finish({ status: "paid" });
        } catch (err) {
          finish({
            status: "failed",
            message:
              err instanceof Error
                ? `${err.message} If money was taken, your plan will switch on within a few minutes.`
                : "We couldn't confirm the payment yet.",
          });
        }
      },
      modal: { ondismiss: () => finish({ status: "dismissed" }) },
    });
    rzp.on("payment.failed", (resp) => {
      // Razorpay keeps the window open so the user can try another method; this only reports.
      if (resp?.error?.description) console.warn("Razorpay payment failed:", resp.error.description);
    });
    rzp.open();
  });
}

export function cancelSubscription(id: string) {
  return apiClient<{ id: string; status: string; cancel_at_period_end: boolean }>(
    `/billing/subscriptions/${id}/cancel`,
    { method: "POST" },
  );
}
