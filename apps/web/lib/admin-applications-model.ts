/** Staff overrides of application status: labels, what an override may set, and the reason rule. Pure. */

export const APPLICATION_STATUSES = [
  "submitted",
  "under_review",
  "reviewing",
  "accepted",
  "approved",
  "rejected",
  "withdrawn",
] as const;
export type ApplicationStatus = (typeof APPLICATION_STATUSES)[number];

export const STATUS_LABELS: Record<string, string> = {
  submitted: "Submitted",
  under_review: "Under review",
  reviewing: "Under review",
  accepted: "Accepted",
  approved: "Accepted",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export type BadgeTone = "default" | "success" | "warning" | "danger" | "info";

export function statusTone(status: string): BadgeTone {
  if (status === "accepted" || status === "approved") return "success";
  if (status === "rejected") return "danger";
  if (status === "withdrawn") return "default";
  if (status === "submitted") return "info";
  return "warning";
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status.replace(/_/g, " ");
}

/** What staff can move an application to: one choice per meaning, never its current status or back to submitted. */
export function overrideTargets(current: string): ApplicationStatus[] {
  const choices: ApplicationStatus[] = ["under_review", "accepted", "rejected", "withdrawn"];
  const same = (s: string) => statusLabel(s) === statusLabel(current);
  return choices.filter((s) => !same(s));
}

export const REASON_MIN = 5;
export const REASON_MAX = 500;

/** Null when the reason is fine, otherwise what to fix. */
export function reasonProblem(reason: string): string | null {
  const text = reason.trim();
  if (text.length < REASON_MIN) return "Say why you're changing it (at least 5 characters).";
  if (text.length > REASON_MAX) return `Keep it under ${REASON_MAX} characters.`;
  return null;
}
