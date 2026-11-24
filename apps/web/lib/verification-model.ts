/** Pure helpers for trust badges and email verification (no imports, so node tests can load it). */

export type EmailKind = "work_email" | "student_email";

const BADGE_LABELS: Record<string, string> = {
  phone: "Mobile",
  work_email: "Work email",
  student_email: "College email",
};

export function badgeLabel(badge: string): string {
  return BADGE_LABELS[badge] ?? badge.replace(/_/g, " ");
}

/** "Mobile • Work email (acme.com)" or a prompt when nothing is verified yet. */
export function trustSummary(
  badges: readonly string[] | undefined,
  verifications: readonly { verification_type: string; email_domain?: string | null }[] = [],
): string {
  if (!badges || badges.length === 0) return "Nothing verified yet";
  return badges
    .map((b) => {
      const domain = verifications.find((v) => v.verification_type === b)?.email_domain;
      return domain ? `${badgeLabel(b)} (${domain})` : badgeLabel(b);
    })
    .join(" • ");
}

const FREE_DOMAINS = new Set([
  "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.in", "outlook.com", "outlook.in",
  "hotmail.com", "live.com", "icloud.com", "me.com", "proton.me", "protonmail.com", "rediffmail.com",
  "zoho.com", "aol.com",
]);

/**
 * Quick client-side hint before sending; the server applies the full rules.
 * Returns a message for the user, or null when the address looks usable.
 */
export function emailHint(email: string, kind: EmailKind): string | null {
  const match = /^[^\s@]+@([^\s@]+\.[^\s@]+)$/.exec(email.trim().toLowerCase());
  if (!match) return "Enter a valid email address";
  const domain = match[1];
  if (FREE_DOMAINS.has(domain)) {
    return "Use the address your employer or college gave you. Personal mailboxes like Gmail can't be verified.";
  }
  if (kind === "student_email" && !/(^|\.)(edu|(ac|edu)\.[a-z]{2})$/.test(domain)) {
    return "College emails must use an academic domain such as .ac.in, .edu or .edu.in.";
  }
  return null;
}
