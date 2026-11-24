import { test } from "node:test";
import assert from "node:assert/strict";
import { planBenefits, priceLabel, pricingHref, subscriptionLabel, upgradeFrom } from "../lib/billing-model.ts";

test("402 upgrade responses become a hint; other errors don't", () => {
  const err = { status: 402, detail: "You've used today's 25 likes.", raw: { plan: "seeker_pro", feature: "unlimited_likes" } };
  assert.deepEqual(upgradeFrom(err), { message: "You've used today's 25 likes.", plan: "seeker_pro", feature: "unlimited_likes" });
  assert.equal(upgradeFrom({ status: 403, detail: "no" }), null);
  assert.equal(upgradeFrom(new Error("boom")), null);
  assert.equal(upgradeFrom(null), null);
  assert.equal(upgradeFrom({ status: 402, raw: {} })?.plan, "");
  assert.equal(pricingHref("owner_pro"), "/pricing?plan=owner_pro");
});

test("prices read naturally in rupees", () => {
  assert.equal(priceLabel({ price_inr: "199.00", period: "monthly", interval: 1 }), "₹199 / month");
  assert.equal(priceLabel({ price_inr: 1499, period: "monthly", interval: 3 }), "₹1,499 / 3 months");
  assert.equal(priceLabel({ price_inr: "99.50", period: "weekly", interval: 1 }), "₹99.5 / week");
});

test("plan features are described in plain language", () => {
  assert.deepEqual(planBenefits({ who_liked_me: true, daily_likes: null }), ["See everyone who liked you", "Unlimited likes"]);
  assert.deepEqual(planBenefits({ max_active_listings: null, featured_slots: 3 }), [
    "Publish as many listings as you like",
    "Feature 3 listings at the top of search",
  ]);
  assert.deepEqual(planBenefits({ featured_slots: 1, max_active_listings: 5 }), [
    "Up to 5 published listings",
    "Feature 1 listing at the top of search",
  ]);
});

test("subscription status says when it renews or ends", () => {
  const now = new Date("2026-11-24T00:00:00Z");
  const end = "2026-12-24T00:00:00Z";
  assert.match(subscriptionLabel({ status: "active", renews: true, is_live: true, expires_at: end }, now), /^Renews on /);
  assert.match(subscriptionLabel({ status: "active", renews: false, is_live: true, expires_at: end }, now), /Won't renew/);
  assert.match(subscriptionLabel({ status: "pending", renews: true, is_live: true, expires_at: end }, now), /retry/);
  assert.equal(subscriptionLabel({ status: "cancelled", renews: false, is_live: false, expires_at: "2026-10-01T00:00:00Z" }, now), "Ended");
});
