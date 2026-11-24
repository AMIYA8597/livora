// Image hosts the Next.js optimizer may fetch from. Shared by next.config.mjs (remotePatterns)
// and ListingImage, which falls back to an unoptimized image for any other host instead of
// failing to render.

const STATIC_HOSTS = [
  { protocol: "https", hostname: "images.unsplash.com" },
  { protocol: "https", hostname: "*.supabase.co" },
];

/** Local API origins serve uploaded files in development and e2e builds. */
export function isLocalHost(hostname) {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
}

/** remotePatterns for next.config: the static hosts plus the API origin (for local uploads). */
export function remotePatterns(apiUrl) {
  const patterns = [...STATIC_HOSTS];
  try {
    const api = new URL(apiUrl);
    patterns.push({
      protocol: api.protocol.replace(":", ""),
      hostname: api.hostname,
      ...(api.port ? { port: api.port } : {}),
      pathname: "/uploads/**",
    });
  } catch {
    /* no API URL: static hosts only */
  }
  return patterns;
}

function hostMatches(pattern, hostname) {
  if (pattern.startsWith("*.")) return hostname.endsWith(pattern.slice(1));
  return pattern === hostname;
}

/** True when `src` can go through the optimizer under the given patterns. */
export function optimizable(src, patterns) {
  if (!src) return false;
  if (src.startsWith("/") && !src.startsWith("//")) return true;
  try {
    const url = new URL(src);
    return patterns.some(
      (p) =>
        url.protocol === `${p.protocol}:` &&
        hostMatches(p.hostname, url.hostname) &&
        (!p.port || p.port === url.port) &&
        (!p.pathname || url.pathname.startsWith(p.pathname.replace(/\*\*$/, ""))),
    );
  } catch {
    return false;
  }
}
