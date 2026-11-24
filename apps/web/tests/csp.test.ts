import { test } from "node:test";
import assert from "node:assert/strict";

import { buildCsp, originOf, sentryEndpoints, socketOrigin } from "../lib/csp.mjs";

const directive = (csp: string, name: string) =>
  csp.split("; ").find((d) => d.startsWith(`${name} `))?.split(" ").slice(1) ?? [];

test("production policy pins script, connect and frame sources", () => {
  const csp = buildCsp({ apiUrl: "https://api.flatmate.in/api/v1" });
  assert.deepEqual(directive(csp, "script-src"), ["'self'", "'unsafe-inline'", "https://checkout.razorpay.com"]);
  assert.ok(directive(csp, "connect-src").includes("https://api.flatmate.in"));
  assert.ok(directive(csp, "connect-src").includes("wss://api.flatmate.in"));
  assert.deepEqual(directive(csp, "object-src"), ["'none'"]);
  assert.deepEqual(directive(csp, "frame-ancestors"), ["'none'"]);
  assert.deepEqual(directive(csp, "form-action"), ["'self'"]);
  assert.ok(csp.includes("upgrade-insecure-requests"));
  assert.ok(!csp.includes("unsafe-eval"));
  assert.ok(!csp.includes("report-uri"));
});

test("dev allows eval and HMR sockets but never upgrades requests", () => {
  const csp = buildCsp({ apiUrl: "http://localhost:8000/api/v1", dev: true });
  assert.ok(directive(csp, "script-src").includes("'unsafe-eval'"));
  assert.ok(directive(csp, "connect-src").includes("ws:"));
  assert.ok(directive(csp, "img-src").includes("http://localhost:8000"));
  assert.ok(!csp.includes("upgrade-insecure-requests"));
});

test("a local production build on http doesn't upgrade its API calls", () => {
  const csp = buildCsp({ apiUrl: "http://localhost:8000/api/v1" });
  assert.ok(!csp.includes("upgrade-insecure-requests"));
  assert.ok(!csp.includes("unsafe-eval"));
});

test("Sentry ingest is allowed and receives CSP reports when a DSN is set", () => {
  const dsn = "https://abc123@o42.ingest.sentry.io/7";
  assert.deepEqual(sentryEndpoints(dsn), {
    origin: "https://o42.ingest.sentry.io",
    reportUri: "https://o42.ingest.sentry.io/api/7/security/?sentry_key=abc123",
  });
  const csp = buildCsp({ apiUrl: "https://api.flatmate.in/api/v1", sentryDsn: dsn });
  assert.ok(directive(csp, "connect-src").includes("https://o42.ingest.sentry.io"));
  assert.ok(csp.endsWith("report-uri https://o42.ingest.sentry.io/api/7/security/?sentry_key=abc123"));
});

test("explicit socket URL wins; bad URLs are ignored", () => {
  assert.equal(socketOrigin("https://api.x.in/api/v1", "wss://ws.x.in/messaging/ws"), "wss://ws.x.in");
  assert.equal(originOf("not a url"), null);
  assert.deepEqual(sentryEndpoints("garbage"), { origin: null, reportUri: null });
  const csp = buildCsp({ apiUrl: "nonsense" });
  assert.deepEqual(directive(csp, "connect-src"), ["'self'", "https://api.razorpay.com", "https://lumberjack.razorpay.com"]);
});
