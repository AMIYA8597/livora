/**
 * Deep links: which website links the Android and iOS apps open instead of the browser, and the
 * two files that prove the apps belong to this site.
 *
 *  - Android App Links: /.well-known/assetlinks.json names the app's package and signing-key
 *    fingerprints. Which paths the app opens is set in the app's own intent filters; use
 *    APP_LINK_PATHS so both stay in step.
 *  - iOS Universal Links: /.well-known/apple-app-site-association names the app ids
 *    (TEAMID.bundle.id) and the paths. Also enables password autofill (webcredentials).
 *
 * Both are configured with server-only environment variables and answer 404 until set:
 *   ANDROID_APP_PACKAGE                e.g. app.flatmate.android
 *   ANDROID_APP_SHA256_FINGERPRINTS    comma-separated, e.g. the Play App Signing key's
 *                                      SHA-256 (AB:CD:...); add the upload key for testing
 *   IOS_APP_IDS                        comma-separated TEAMID.bundle.id
 *
 * Notification links (`Notification.link`) are paths on this site, so a push opened on a phone
 * lands on the same screen the website would show.
 */

/** Paths the apps open. Sign-in, password reset, admin and legal pages stay on the web. */
export const APP_LINK_PATHS = [
  "/properties",
  "/properties/*",
  "/flatmates",
  "/flatmates/*",
  "/messages",
  "/messages/*",
  "/notifications",
  "/matches",
  "/matches/*",
  "/appointments",
  "/appointments/*",
  "/groups",
  "/groups/*",
  "/pg/*",
  "/owner",
  "/owner/*",
  "/dashboard",
  "/profile",
] as const;

const ANDROID_PACKAGE = /^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$/;
const SHA256_FINGERPRINT = /^([0-9A-F]{2}:){31}[0-9A-F]{2}$/;
const IOS_APP_ID = /^[A-Z0-9]{10}\.[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/;

type Env = Record<string, string | undefined>;

function list(value: string | undefined): string[] {
  return (value ?? "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

export interface AssetLink {
  relation: string[];
  target: { namespace: "android_app"; package_name: string; sha256_cert_fingerprints: string[] };
}

/** The assetlinks.json statements, or null when Android isn't configured (answer 404). */
export function assetLinks(env: Env): AssetLink[] | null {
  const pkg = (env.ANDROID_APP_PACKAGE ?? "").trim();
  const fingerprints = list(env.ANDROID_APP_SHA256_FINGERPRINTS)
    .map((f) => f.toUpperCase())
    .filter((f) => SHA256_FINGERPRINT.test(f));
  if (!ANDROID_PACKAGE.test(pkg) || fingerprints.length === 0) return null;
  return [
    {
      relation: ["delegate_permission/common.handle_all_urls", "delegate_permission/common.get_login_creds"],
      target: { namespace: "android_app", package_name: pkg, sha256_cert_fingerprints: fingerprints },
    },
  ];
}

export interface AppleAppSiteAssociation {
  applinks: { details: { appIDs: string[]; components: { "/": string; comment?: string }[] }[] };
  webcredentials: { apps: string[] };
}

/** The apple-app-site-association document, or null when iOS isn't configured (answer 404). */
export function appleAppSiteAssociation(env: Env): AppleAppSiteAssociation | null {
  const appIds = list(env.IOS_APP_IDS).filter((id) => IOS_APP_ID.test(id));
  if (appIds.length === 0) return null;
  return {
    applinks: { details: [{ appIDs: appIds, components: APP_LINK_PATHS.map((path) => ({ "/": path })) }] },
    webcredentials: { apps: appIds },
  };
}

/** Whether the apps open this path (mirrors the patterns above: exact, or "/x/*" for below /x). */
export function opensInApp(path: string): boolean {
  const clean = path.split(/[?#]/)[0].replace(/\/+$/, "") || "/";
  return APP_LINK_PATHS.some((pattern) =>
    pattern.endsWith("/*") ? clean.startsWith(pattern.slice(0, -1)) && clean.length > pattern.length - 1 : clean === pattern,
  );
}
