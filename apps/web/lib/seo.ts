/** Search and link-preview data for listings. Pure, so it's tested without a server. */
import type { PropertyDTO } from "@flatmate/contracts";

const CONFIG_LABELS: Record<string, string> = {
  "1RK": "1 RK", "1BHK": "1 BHK", "2BHK": "2 BHK", "3BHK": "3 BHK", "4BHK_plus": "4+ BHK", studio: "Studio",
};
const CATEGORY_LABELS: Record<string, string> = {
  apartment: "flat", pg: "PG", independent_house: "house", hostel: "hostel", co_living: "co-living space",
};

export function truncate(text: string, max: number): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max - 1);
  const lastSpace = cut.lastIndexOf(" ");
  return `${(lastSpace > max * 0.6 ? cut.slice(0, lastSpace) : cut).replace(/[\s,.;:–-]+$/, "")}…`;
}

/** The API sends money as decimal strings ("18000.00"); accept either. */
export function toAmount(value: number | string | null | undefined): number {
  const n = typeof value === "string" ? Number.parseFloat(value) : Number(value);
  return Number.isFinite(n) ? n : NaN;
}

export function formatRent(value: number | string, currency = "INR"): string {
  const amount = toAmount(value);
  if (!Number.isFinite(amount)) return "";
  if (currency === "INR") return `₹${Math.round(amount).toLocaleString("en-IN")}`;
  return `${currency} ${Math.round(amount).toLocaleString("en-IN")}`;
}

type ListingLike = Pick<PropertyDTO, "id" | "title" | "description" | "city" | "monthly_rent"> &
  Partial<Pick<PropertyDTO, "currency" | "address_display" | "configuration" | "property_category" | "images" | "available_from">>;

/** "2 BHK flat in Indiranagar, Bengaluru · ₹18,000/month" */
export function listingHeadline(p: ListingLike): string {
  const config = p.configuration ? CONFIG_LABELS[p.configuration] ?? p.configuration : "";
  const kind = p.property_category ? CATEGORY_LABELS[p.property_category] ?? "place" : "place";
  const where = p.address_display?.trim() || p.city;
  const what = [config, kind].filter(Boolean).join(" ");
  return `${what.charAt(0).toUpperCase()}${what.slice(1)} in ${where} · ${formatRent(p.monthly_rent, p.currency)}/month`;
}

/** Absolute URL for an image path: listing photos may be stored as API-relative paths locally. */
export function absoluteImage(src: string | undefined, apiOrigin: string): string | undefined {
  if (!src) return undefined;
  if (/^https?:\/\//i.test(src)) return src;
  if (src.startsWith("/")) return `${apiOrigin}${src}`;
  return undefined;
}

export function listingMetadata(p: ListingLike, siteUrl: string, apiOrigin: string) {
  const url = `${siteUrl}/properties/${p.id}`;
  const title = truncate(p.title, 60);
  const description = truncate(`${listingHeadline(p)}. ${p.description || ""}`, 160);
  const image = absoluteImage(p.images?.[0], apiOrigin);
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      type: "website" as const,
      url,
      title,
      description,
      siteName: "Flatmate",
      locale: "en_IN",
      ...(image ? { images: [{ url: image, alt: p.title }] } : {}),
    },
    twitter: {
      card: image ? ("summary_large_image" as const) : ("summary" as const),
      title,
      description,
      ...(image ? { images: [image] } : {}),
    },
  };
}

/** schema.org data for a listing, as an Offer for a place to rent. */
export function listingJsonLd(p: ListingLike, siteUrl: string, apiOrigin: string): Record<string, unknown> {
  const images = (p.images ?? []).map((i) => absoluteImage(i, apiOrigin)).filter(Boolean);
  return {
    "@context": "https://schema.org",
    "@type": "Offer",
    url: `${siteUrl}/properties/${p.id}`,
    name: p.title,
    description: truncate(p.description || listingHeadline(p), 500),
    price: Math.round(toAmount(p.monthly_rent)),
    priceCurrency: p.currency || "INR",
    priceSpecification: {
      "@type": "UnitPriceSpecification",
      price: Math.round(toAmount(p.monthly_rent)),
      priceCurrency: p.currency || "INR",
      unitCode: "MON",
    },
    ...(p.available_from ? { availabilityStarts: p.available_from } : {}),
    itemOffered: {
      "@type": "Accommodation",
      name: p.title,
      address: {
        "@type": "PostalAddress",
        addressLocality: p.city,
        ...(p.address_display ? { streetAddress: p.address_display } : {}),
        addressCountry: "IN",
      },
      ...(images.length ? { image: images } : {}),
    },
  };
}

/** JSON for an inline <script type="application/ld+json">: "<" can't end the script early. */
export function jsonLdString(data: unknown): string {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}
