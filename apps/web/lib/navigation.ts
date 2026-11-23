/**
 * Where to send the user after sign-in. Only same-site absolute paths are allowed, so a crafted
 * `?next=https://evil.example` or `?next=//evil.example` cannot turn login into an open redirect.
 */
export function safeNextPath(raw: string | null | undefined, fallback = "/dashboard"): string {
  if (!raw) return fallback;
  let value: string;
  try {
    value = decodeURIComponent(raw).trim();
  } catch {
    return fallback;
  }
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\") || /[\u0000-\u001f]/.test(value)) {
    return fallback;
  }
  // Never bounce back into the auth pages themselves.
  if (/^\/(login|register)(\/|\?|$)/.test(value)) return fallback;
  return value;
}

/** Login URL that returns the user to `path` afterwards. */
export function loginHref(path: string): string {
  return `/login?next=${encodeURIComponent(path)}`;
}
