import { withSentryConfig } from "@sentry/nextjs/config";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Dev only: let http://127.0.0.1:3000 (the host in .env.local) load dev resources such as HMR.
  allowedDevOrigins: ["127.0.0.1"],
  reactStrictMode: true,
  transpilePackages: ["@flatmate/ui", "@flatmate/contracts"],
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
      {
        protocol: "http",
        hostname: "localhost",
      },
      {
        protocol: "https",
        hostname: "*.supabase.co",
      },
    ],
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-XSS-Protection",
            value: "1; mode=block",
          },
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
