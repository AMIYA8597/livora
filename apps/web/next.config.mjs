import { withSentryConfig } from "@sentry/nextjs/config";
import { buildCsp } from "./lib/csp.mjs";
import { isLocalHost, remotePatterns } from "./lib/image-hosts.mjs";

const isDev = process.env.NODE_ENV !== "production";
const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const apiIsLocal = (() => {
  try {
    return isLocalHost(new URL(apiUrl).hostname);
  } catch {
    return false;
  }
})();
const csp = buildCsp({
  apiUrl,
  wsUrl: process.env.NEXT_PUBLIC_WS_URL,
  sentryDsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  dev: isDev,
});
// CSP_REPORT_ONLY=true sends the policy as report-only (violations are reported, nothing is
// blocked): useful for a first deploy to a new domain.
const cspHeader = process.env.CSP_REPORT_ONLY === "true" ? "Content-Security-Policy-Report-Only" : "Content-Security-Policy";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Dev only: let http://127.0.0.1:3000 (the host in .env.local) load dev resources such as HMR.
  allowedDevOrigins: ["127.0.0.1"],
  reactStrictMode: true,
  transpilePackages: ["@flatmate/ui", "@flatmate/contracts"],
  images: {
    // Listing photos: AVIF/WebP at the sizes each layout asks for, cached for a day.
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 86400,
    remotePatterns: remotePatterns(apiUrl),
    // Local builds read uploads from the API on localhost, which the optimizer refuses by default.
    dangerouslyAllowLocalIP: apiIsLocal,
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: cspHeader,
            value: csp,
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            // The old XSS auditor is gone from browsers and could be abused; CSP replaces it.
            key: "X-XSS-Protection",
            value: "0",
          },
          ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=31536000" }]),
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(self)",
          },
          {
            key: "X-Robots-Tag",
            value: process.env.NODE_ENV === "production" && process.env.ENVIRONMENT === "production" ? "all" : "noindex, nofollow",
          },
        ],
      },
    ];
  },
};

/**
 * Error tracking is built in only when NEXT_PUBLIC_SENTRY_DSN is set. Source maps are uploaded (and
 * then deleted from the deploy) only when SENTRY_AUTH_TOKEN, SENTRY_ORG and SENTRY_PROJECT are set too.
 */
const canUploadSourceMaps = !!(process.env.SENTRY_AUTH_TOKEN && process.env.SENTRY_ORG && process.env.SENTRY_PROJECT);

export default process.env.NEXT_PUBLIC_SENTRY_DSN
  ? withSentryConfig(nextConfig, {
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      authToken: process.env.SENTRY_AUTH_TOKEN,
      silent: !process.env.CI,
      telemetry: false,
      sourcemaps: { disable: !canUploadSourceMaps },
    })
  : nextConfig;
