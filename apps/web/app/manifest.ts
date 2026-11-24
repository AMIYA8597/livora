import type { MetadataRoute } from "next";

/** Installable app (the website until the Android and iOS apps ship; also needed for push on
 *  iPhone/iPad, which only works from the Home Screen). Icons come from app/icons/[name]. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Flatmate",
    short_name: "Flatmate",
    description: "Find your place. Find your people.",
    lang: "en-IN",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#FAF8F5",
    theme_color: "#173D32",
    categories: ["lifestyle"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
      { src: "/logo.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
    ],
    shortcuts: [
      { name: "Find a room", url: "/properties", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "Find flatmates", url: "/flatmates", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "Messages", url: "/messages", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
    ],
  };
}
