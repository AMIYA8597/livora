/**
 * Moderation report statuses as the API stores them (app/modules/moderation/models.py):
 * new reports, user-filed or automatic, start "open".
 */
export const REPORT_STATUSES = ["open", "under_investigation", "resolved", "dismissed"] as const;
export type ReportStatus = (typeof REPORT_STATUSES)[number];

/** Still waiting for a moderator: show it in the queue count and offer resolve/dismiss. */
export function reportNeedsAction(status: string): boolean {
  return status === "open" || status === "under_investigation";
}
