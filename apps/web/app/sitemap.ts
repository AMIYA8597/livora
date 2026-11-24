import type { MetadataRoute } from "next";
import { fetchListingIdsForSitemap } from "@/lib/server-api";
import { siteUrl } from "@/lib/site";

/** Rebuilt at most hourly: public pages plus every published listing. */
export const revalidate = 3600;

const PUBLIC_PAGES: { path: string; priority: number; changeFrequency: "hourly" | "daily" | "weekly" | "monthly" }[] = [
  { path: "", priority: 1, changeFrequency: "daily" },
  { path: "/properties", priority: 0.9, changeFrequency: "hourly" },
  { path: "/flatmates", priority: 0.8, changeFrequency: "daily" },
  { path: "/pg", priority: 0.8, changeFrequency: "daily" },
  { path: "/tenants", priority: 0.6, changeFrequency: "weekly" },
  { path: "/groups", priority: 0.6, changeFrequency: "daily" },
  { path: "/pricing", priority: 0.5, changeFrequency: "monthly" },
  { path: "/about", priority: 0.4, changeFrequency: "monthly" },
  { path: "/safety", priority: 0.4, changeFrequency: "monthly" },
  { path: "/help", priority: 0.4, changeFrequency: "monthly" },
  { path: "/terms", priority: 0.2, changeFrequency: "monthly" },
  { path: "/privacy", priority: 0.2, changeFrequency: "monthly" },
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteUrl();
  const now = new Date();
  const listings = await fetchListingIdsForSitemap();
  return [
    ...PUBLIC_PAGES.map(({ path, priority, changeFrequency }) => ({
      url: `${base}${path}`,
      lastModified: now,
      changeFrequency,
      priority,
    })),
    ...listings.map(({ id, updated }) => ({
      url: `${base}/properties/${id}`,
      lastModified: updated ? new Date(updated) : now,
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
  ];
}
