import type { MetadataRoute } from "next";
import { indexable, PRIVATE_PATHS, siteUrl } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  if (!indexable()) {
    // Staging, previews and local builds stay out of search results.
    return { rules: [{ userAgent: "*", disallow: "/" }] };
  }
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: PRIVATE_PATHS }],
    sitemap: `${siteUrl()}/sitemap.xml`,
    host: siteUrl(),
  };
}
