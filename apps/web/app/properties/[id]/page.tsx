import type { Metadata } from "next";
import { originOf } from "@/lib/csp.mjs";
import { fetchPublicListing } from "@/lib/server-api";
import { jsonLdString, listingJsonLd, listingMetadata } from "@/lib/seo";
import { publicApiBase, siteUrl } from "@/lib/site";
import { PropertyDetail } from "./PropertyDetail";

type Params = Promise<{ id: string }>;

// Links to uploaded photos go to the public API address, not the private one the server fetches from.
const apiOrigin = () => originOf(publicApiBase()) ?? "";

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  const listing = await fetchPublicListing(id);
  if (listing.kind !== "found") {
    // Unpublished, removed, or the API was unreachable: nothing to show search engines.
    return { title: "Listing", robots: { index: false, follow: true } };
  }
  return listingMetadata(listing.property, siteUrl(), apiOrigin());
}

export default async function PropertyPage({ params }: { params: Params }) {
  const { id } = await params;
  const listing = await fetchPublicListing(id);
  const property = listing.kind === "found" ? listing.property : undefined;
  return (
    <>
      {property && (
        <script
          type="application/ld+json"
          // JSON only, with "<" escaped: see jsonLdString.
          dangerouslySetInnerHTML={{ __html: jsonLdString(listingJsonLd(property, siteUrl(), apiOrigin())) }}
        />
      )}
      <PropertyDetail initialProperty={property} />
    </>
  );
}
