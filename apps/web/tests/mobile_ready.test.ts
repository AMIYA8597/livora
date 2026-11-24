import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import manifest from "../app/manifest.ts";
import { APP_LINK_PATHS, appleAppSiteAssociation, assetLinks, opensInApp } from "../lib/deep-links.ts";

const FINGERPRINT = Array.from({ length: 32 }, (_, i) => (i * 7).toString(16).padStart(2, "0").slice(-2)).join(":");

test("assetlinks.json appears only when Android is configured, with valid values only", () => {
  assert.equal(assetLinks({}), null);
  assert.equal(assetLinks({ ANDROID_APP_PACKAGE: "app.flatmate", ANDROID_APP_SHA256_FINGERPRINTS: "nope" }), null);
  assert.equal(assetLinks({ ANDROID_APP_PACKAGE: "flatmate", ANDROID_APP_SHA256_FINGERPRINTS: FINGERPRINT }), null);

  const links = assetLinks({
    ANDROID_APP_PACKAGE: " app.flatmate.android ",
    ANDROID_APP_SHA256_FINGERPRINTS: `${FINGERPRINT}, bad, ${FINGERPRINT.toLowerCase().replace(/^../, "ff")}`,
  });
  assert.ok(links);
  assert.deepEqual(links[0].relation, [
    "delegate_permission/common.handle_all_urls",
    "delegate_permission/common.get_login_creds",
  ]);
  assert.equal(links[0].target.package_name, "app.flatmate.android");
  assert.deepEqual(links[0].target.sha256_cert_fingerprints, [
    FINGERPRINT.toUpperCase(),
    FINGERPRINT.toUpperCase().replace(/^../, "FF"),
  ]);
});

test("apple-app-site-association lists the app ids and the in-app paths", () => {
  assert.equal(appleAppSiteAssociation({}), null);
  assert.equal(appleAppSiteAssociation({ IOS_APP_IDS: "app.flatmate.ios" }), null); // no team id
  const doc = appleAppSiteAssociation({ IOS_APP_IDS: "ABCDE12345.app.flatmate.ios, bad id" });
  assert.ok(doc);
  assert.deepEqual(doc.applinks.details[0].appIDs, ["ABCDE12345.app.flatmate.ios"]);
  assert.deepEqual(doc.webcredentials.apps, ["ABCDE12345.app.flatmate.ios"]);
  assert.deepEqual(
    doc.applinks.details[0].components.map((c) => c["/"]),
    [...APP_LINK_PATHS],
  );
});

test("the apps open product screens; sign-in, admin and legal pages stay on the web", () => {
  for (const path of ["/properties/abc", "/properties", "/messages?conversationId=1", "/notifications",
    "/flatmates/9", "/appointments", "/owner/listings/new", "/matches/"]) {
    assert.equal(opensInApp(path), true, path);
  }
  for (const path of ["/", "/login", "/reset-password?token=x", "/admin", "/privacy", "/terms",
    "/pricing", "/propertiesx", "/pg"]) {
    assert.equal(opensInApp(path), false, path);
  }
});

test("the manifest is installable on Android and iPhone", () => {
  const m = manifest();
  assert.equal(m.display, "standalone");
  assert.equal(m.id, "/");
  const sizes = (m.icons ?? []).map((i) => `${i.sizes} ${i.purpose}`);
  assert.ok(sizes.includes("192x192 any") && sizes.includes("512x512 any") && sizes.includes("512x512 maskable"));
  for (const shortcut of m.shortcuts ?? []) assert.ok(opensInApp(shortcut.url), shortcut.url);
});

test("the service worker caches only the offline page and leaves API calls alone", () => {
  const sw = readFileSync(new URL("../public/sw.js", import.meta.url), "utf8");
  assert.match(sw, /OFFLINE_URL = "\/offline\.html"/);
  assert.match(sw, /request\.mode !== "navigate"/);
  assert.doesNotMatch(sw, /cache\.put|cache\.addAll/);
  const page = readFileSync(new URL("../public/offline.html", import.meta.url), "utf8");
  assert.match(page, /You're offline/);
});
