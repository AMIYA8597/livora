import { test } from "node:test";
import assert from "node:assert/strict";

import {
  absoluteImage, formatRent, jsonLdString, listingHeadline, listingJsonLd, listingMetadata, truncate,
} from "../lib/seo.ts";
import { indexable, publicApiBase, serverApiBase, siteUrl } from "../lib/site.ts";
import { optimizable, remotePatterns } from "../lib/image-hosts.mjs";

const listing = {
  id: "0b6f1c1e-2a4b-4c8d-9e0f-123456789abc",
  title: "Sunny 2BHK near Indiranagar metro",
  description: "Bright flat, fully furnished, 5 minutes from the metro. Looking for a quiet working professional.",
  city: "Bengaluru",
  address_display: "Indiranagar, Bengaluru",
  monthly_rent: 18000,
  currency: "INR",
  configuration: "2BHK" as const,
  property_category: "apartment" as const,
  images: ["/uploads/properties/prop_x/a.jpg", "https://images.unsplash.com/p.jpg"],
  available_from: "2026-12-01",
};

test("headline reads like a search result", () => {
  assert.equal(listingHeadline(listing), "2 BHK flat in Indiranagar, Bengaluru · ₹18,000/month");
  assert.equal(listingHeadline({ ...listing, configuration: undefined, property_category: "pg", address_display: "" }),
    "PG in Bengaluru · ₹18,000/month");
  assert.equal(formatRent(125000), "₹1,25,000");
});

test("truncate cuts on a word and marks it", () => {
  assert.equal(truncate("short", 10), "short");
  const cut = truncate("a quiet furnished room near the metro station", 25);
  assert.ok(cut.length <= 25 && cut.endsWith("…"), cut);
  assert.ok(!cut.includes("  "));
});

test("metadata has a canonical URL, a 160-char description and the first photo", () => {
  const m = listingMetadata(listing, "https://flatmate.in", "http://127.0.0.1:8000");
  assert.equal(m.alternates.canonical, `https://flatmate.in/properties/${listing.id}`);
  assert.ok(m.description.length <= 160);
  assert.ok(m.description.startsWith("2 BHK flat in Indiranagar"));
  assert.deepEqual(m.openGraph.images, [{ url: "http://127.0.0.1:8000/uploads/properties/prop_x/a.jpg", alt: listing.title }]);
  assert.equal(m.twitter.card, "summary_large_image");
  const noPhotos = listingMetadata({ ...listing, images: [] }, "https://flatmate.in", "");
  assert.equal(noPhotos.twitter.card, "summary");
  assert.equal("images" in noPhotos.openGraph, false);
});

test("structured data describes a monthly rental offer", () => {
  const ld = listingJsonLd(listing, "https://flatmate.in", "https://api.flatmate.in") as any;
  assert.equal(ld["@type"], "Offer");
  assert.equal(ld.price, 18000);
  assert.equal(ld.priceSpecification.unitCode, "MON");
  assert.equal(ld.itemOffered["@type"], "Accommodation");
  assert.equal(ld.itemOffered.address.addressLocality, "Bengaluru");
  assert.deepEqual(ld.itemOffered.image, [
    "https://api.flatmate.in/uploads/properties/prop_x/a.jpg", "https://images.unsplash.com/p.jpg",
  ]);
});

test("JSON-LD can't close its script tag", () => {
  const out = jsonLdString({ name: "</script><script>alert(1)</script>", sep: "a b" });
  assert.ok(!out.includes("<"));
  assert.ok(!out.includes(" "));
  assert.deepEqual(JSON.parse(out), { name: "</script><script>alert(1)</script>", sep: "a b" });
});

test("only http(s) or API-relative images are used", () => {
  assert.equal(absoluteImage("javascript:alert(1)", "https://api.x"), undefined);
  assert.equal(absoluteImage("relative.jpg", "https://api.x"), undefined);
  assert.equal(absoluteImage(undefined, "https://api.x"), undefined);
});

test("site settings come from the environment", () => {
  assert.equal(siteUrl({ NEXT_PUBLIC_APP_URL: "https://flatmate.in/" }), "https://flatmate.in");
  assert.equal(siteUrl({ NEXT_PUBLIC_APP_URL: "not a url" }), "http://localhost:3000");
  assert.equal(siteUrl({}), "http://localhost:3000");
  assert.equal(indexable({ NODE_ENV: "production", ENVIRONMENT: "production" }), true);
  assert.equal(indexable({ NODE_ENV: "production", ENVIRONMENT: "staging" }), false);
  assert.equal(serverApiBase({ API_INTERNAL_URL: "http://api.internal/api/v1/", NEXT_PUBLIC_API_URL: "https://x" }),
    "http://api.internal/api/v1");
  // Photo links in pages never use the private address.
  assert.equal(publicApiBase({ API_INTERNAL_URL: "http://api:8000/api/v1", NEXT_PUBLIC_API_URL: "https://api.x.in/api/v1/" }),
    "https://api.x.in/api/v1");
});

test("the optimizer only gets hosts it's configured for", () => {
  const patterns = remotePatterns("http://127.0.0.1:8000/api/v1");
  assert.ok(optimizable("https://images.unsplash.com/photo-1?w=800", patterns));
  assert.ok(optimizable("https://abc.supabase.co/storage/v1/object/public/p/a.jpg", patterns));
  assert.ok(optimizable("http://127.0.0.1:8000/uploads/properties/a.jpg", patterns));
  assert.ok(!optimizable("http://127.0.0.1:8000/api/v1/secret", patterns));
  assert.ok(!optimizable("http://127.0.0.1:9999/uploads/a.jpg", patterns));
  assert.ok(!optimizable("https://evil.example/a.jpg", patterns));
  assert.ok(!optimizable("https://supabase.co.evil.example/a.jpg", patterns));
  assert.ok(optimizable("/local.png", patterns));
  assert.ok(!optimizable("//evil.example/a.jpg", patterns));
});

test("rent given as the API's decimal string still formats", () => {
  assert.equal(formatRent("36000.00"), "₹36,000");
  const headline = listingHeadline({ ...listing, monthly_rent: "36000.00" as unknown as number });
  assert.ok(headline.endsWith("₹36,000/month"), headline);
  const ld = listingJsonLd({ ...listing, monthly_rent: "36000.00" as unknown as number }, "https://x", "") as any;
  assert.equal(ld.price, 36000);
});

test("server and browser build the same listings request", async () => {
  const { filtersFromSearch, listingQueryParams, toQueryString } = await import("../lib/listing-query.ts");
  const { queryKey } = await import("../lib/query-key.ts");
  const search = new URLSearchParams("city=Pune&max_rent=20000&page=2&config=2BHK");
  const a = filtersFromSearch((k) => search.get(k));
  const b = filtersFromSearch((k) => ({ city: "Pune", max_rent: "20000", page: "2", config: "2BHK" } as Record<string, string>)[k]);
  assert.equal(queryKey("/properties", listingQueryParams(a.applied, a.page)), queryKey("/properties", listingQueryParams(b.applied, b.page)));
  assert.equal(a.page, 2);
  assert.equal(filtersFromSearch(() => "-3").page, 1);
  assert.equal(toQueryString(listingQueryParams(a.applied, a.page)), "limit=9&offset=9&city=Pune&max_rent=20000&configuration=2BHK");
});
