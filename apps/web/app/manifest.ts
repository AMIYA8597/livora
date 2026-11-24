import type { MetadataRoute } from "next";

/** Installable app (needed for push on iPhone/iPad, which only works from the Home Screen). */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Flatmate",
    short_name: "Flatmate",
    description: "Find your place. Find your people.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#FAF8F5",
    theme_color: "#173D32",
    icons: [{ src: "/logo.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
