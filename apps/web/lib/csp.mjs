// Content-Security-Policy for the web app. Plain ESM so next.config.mjs can import it; the
// tests import it too.
//
// Scripts allow 'unsafe-inline' because Next.js inlines its bootstrap scripts, and a nonce
// would make every page render dynamically (no static or cached pages). The policy still
// pins where scripts, connections, frames and images may come from, blocks plugins, <base>
// hijacking and framing, and keeps forms on this site.

const RAZORPAY_SCRIPT = "https://checkout.razorpay.com";
const RAZORPAY_FRAMES = ["https://api.razorpay.com", "https://checkout.razorpay.com"];
const RAZORPAY_CONNECT = ["https://api.razorpay.com", "https://lumberjack.razorpay.com"];
const IMAGE_HOSTS = ["https://images.unsplash.com", "https://*.supabase.co"];

/** "https://host:port" for a URL, or null when it isn't a valid absolute URL. */
export function originOf(url) {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.origin === "null" ? `${parsed.protocol}//${parsed.host}` : parsed.origin;
  } catch {
    return null;
  }
}

/** Sentry's ingest origin and CSP report endpoint for a DSN, or nulls. */
export function sentryEndpoints(dsn) {
  if (!dsn) return { origin: null, reportUri: null };
  try {
    const url = new URL(dsn);
    const projectId = url.pathname.replace(/^\/+|\/+$/g, "");
    if (!url.username || !projectId) return { origin: url.origin, reportUri: null };
    return {
      origin: url.origin,
      reportUri: `${url.origin}/api/${projectId}/security/?sentry_key=${url.username}`,
    };
  } catch {
    return { origin: null, reportUri: null };
  }
}

/** The WebSocket origin the chat uses: the explicit URL, else the API URL with ws(s). */
export function socketOrigin(apiUrl, wsUrl) {
  if (wsUrl) return originOf(wsUrl);
  const api = originOf(apiUrl);
  return api ? api.replace(/^http/, "ws") : null;
}

/**
 * @param {{ apiUrl?: string, wsUrl?: string, sentryDsn?: string, dev?: boolean }} env
 * @returns {string}
 */
export function buildCsp({ apiUrl, wsUrl, sentryDsn, dev = false } = {}) {
  const api = originOf(apiUrl);
  const ws = socketOrigin(apiUrl, wsUrl);
  const sentry = sentryEndpoints(sentryDsn);
  const unique = (list) => [...new Set(list.filter(Boolean))];

  const directives = {
    "default-src": ["'self'"],
    // Dev mode needs eval for React's debugging and fast refresh; production never does.
    "script-src": unique(["'self'", "'unsafe-inline'", dev && "'unsafe-eval'", RAZORPAY_SCRIPT]),
    "style-src": ["'self'", "'unsafe-inline'"],
    // The API origin serves local-storage uploads in development.
    "img-src": unique(["'self'", "data:", "blob:", ...IMAGE_HOSTS, api]),
    "font-src": ["'self'", "data:"],
    "connect-src": unique(["'self'", api, ws, sentry.origin, ...RAZORPAY_CONNECT, dev && "ws:"]),
    "frame-src": RAZORPAY_FRAMES,
    "worker-src": ["'self'"],
    "manifest-src": ["'self'"],
    "media-src": ["'self'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };

  const parts = Object.entries(directives).map(([name, values]) => `${name} ${values.join(" ")}`);
  // Only when the API is on https too: a local production build talks to http://localhost.
  if (!dev && api?.startsWith("https:")) parts.push("upgrade-insecure-requests");
  if (sentry.reportUri) parts.push(`report-uri ${sentry.reportUri}`);
  return parts.join("; ");
}
