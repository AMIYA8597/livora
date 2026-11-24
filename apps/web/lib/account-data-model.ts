/** Pure helpers for the "your data" controls: export download and account deletion. */

export const DELETION_GRACE_DAYS = 30;

/** "24 December 2026" in the reader's locale-neutral Indian English style; "" for bad input. */
export function deletionDateLabel(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Kolkata" });
}

export function exportFileName(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `flatmate-data-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}.json`;
}

/** The ?deleted= value the login page shows after a deletion request, if it's a real date. */
export function deletedNoticeDate(param: string | null | undefined): string | null {
  const label = deletionDateLabel(param);
  return label || null;
}

/** What happens, in order, shown before someone confirms. */
export function deletionConsequences(): string[] {
  return [
    "Your profile and listings are hidden and you're signed out on every device straight away.",
    `After ${DELETION_GRACE_DAYS} days your account is deleted for good: profile, photos, verifications, ` +
      "matches, applications, viewings and listings.",
    "People with open applications or viewings on your listings are told the listing was removed.",
    "Messages you sent stay in the other person's chat, shown as from \"Deleted user\". Files you sent are removed.",
    "Payment records are kept for accounting, without your name, email or phone.",
    `Changed your mind? Sign in within ${DELETION_GRACE_DAYS} days and everything comes back.`,
  ];
}
