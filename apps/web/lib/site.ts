/**
 * Where the site lives and whether search engines should index it. Set NEXT_PUBLIC_APP_URL to
 * the public origin (e.g. https://flatmate.in); ENVIRONMENT=production, present when the web app
 * is built, turns indexing on.
 */
export function siteUrl(env: Record<string, string | undefined> = process.env): string {
  const raw = (env.NEXT_PUBLIC_APP_URL || "").trim().replace(/\/+$/, "");
  if (raw) {
    try {
      return new URL(raw).origin;
    } catch {
      /* fall through */
    }
  }
  return "http://localhost:3000";
}

export function indexable(env: Record<string, string | undefined> = process.env): boolean {
  return env.NODE_ENV === "production" && env.ENVIRONMENT === "production";
}

/** The API base browsers use (and links in pages must use): never the private address. */
export function publicApiBase(env: Record<string, string | undefined> = process.env): string {
  return (env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/+$/, "");
}

/** The API base for server-side fetches: a private URL when there is one, else the public one. */
export function serverApiBase(env: Record<string, string | undefined> = process.env): string {
  return (env.API_INTERNAL_URL || env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/+$/, "");
}

/** Private areas that must never be indexed (also listed in robots.txt). */
export const PRIVATE_PATHS = [
  "/admin", "/dashboard", "/messages", "/notifications", "/owner", "/profile", "/onboarding",
  "/appointments", "/matches", "/login", "/register", "/forgot-password", "/reset-password",
];
