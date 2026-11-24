import { test } from "node:test";
import assert from "node:assert/strict";
import { redact, scrubEvent, sentryOptions, stripQuery } from "../lib/sentry-scrub.ts";

test("error tracking is off without a DSN", () => {
  assert.equal(sentryOptions({}), null);
  const on = sentryOptions({ dsn: "https://k@o0.ingest.sentry.io/1", tracesSampleRate: "7" });
  assert.ok(on);
  assert.equal(on.sendDefaultPii, false);
  assert.equal(on.tracesSampleRate, 0);
  assert.equal(sentryOptions({ dsn: "x", tracesSampleRate: "0.2" })?.tracesSampleRate, 0.2);
});

test("tokens are redacted and query strings dropped", () => {
  assert.equal(redact("Authorization: Bearer abc.def-ghi"), "Authorization: Bearer [REDACTED]");
  assert.equal(redact('{"password": "hunter2"}'), '{"password": "[REDACTED]"}');
  assert.equal(redact("wss://api/ws?token=xyz&x=1"), "wss://api/ws?token=[REDACTED]&x=1");
  assert.ok(!redact("jwt eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.abcDEF123").includes("eyJ"));
  assert.equal(stripQuery("/messages?conversationId=1#x"), "/messages");
});

test("reports keep nothing personal", () => {
  const out = scrubEvent({
    request: {
      url: "https://flatmate.in/reset-password?token=abc",
      cookies: { a: "b" },
      data: "body",
      query_string: "token=abc",
      headers: { Authorization: "Bearer x", "User-Agent": "UA", Cookie: "c" },
    },
    user: { id: "u1", email: "a@b.com", ip_address: "1.2.3.4" },
    exception: { values: [{ value: "failed with Bearer abc.def" }] },
    breadcrumbs: [{ message: '{"otp": "123456"}', data: { url: "/api?code=9", from: "/a?x=1", to: "/b?y=2" } }],
  });
  assert.deepEqual(out.request, { url: "https://flatmate.in/reset-password", headers: { "User-Agent": "UA" } });
  assert.deepEqual(out.user, { id: "u1" });
  assert.ok(!out.exception.values[0].value.includes("abc.def"));
  assert.ok(!out.breadcrumbs[0].message.includes("123456"));
  assert.deepEqual(out.breadcrumbs[0].data, { url: "/api", from: "/a", to: "/b" });
});
