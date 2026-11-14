import { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = "https://flatmate.platform";
  const now = new Date();

  const routes = [
    "",
    "/properties",
    "/flatmates",
    "/matches",
    "/groups",
    "/about",
    "/safety",
    "/help",
    "/terms",
    "/privacy",
    "/tenants",
    "/pg",
  ];

  return routes.map((route) => ({
    url: `${baseUrl}${route}`,
    lastModified: now,
    changeFrequency: route === "" || route === "/properties" || route === "/flatmates" ? "hourly" : "weekly",
    priority: route === "" ? 1.0 : route === "/properties" || route === "/flatmates" ? 0.9 : 0.7,
  }));
}
