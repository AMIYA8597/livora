/** Wording for an application's status timeline, from the viewer's side. Pure. */
import type { ApplicationTimelineEntryDTO } from "@flatmate/contracts";
import { statusLabel } from "./admin-applications-model.ts";

export type TimelineViewer = "applicant" | "owner";

export function actorLabel(actor: ApplicationTimelineEntryDTO["actor"], viewer: TimelineViewer): string {
  if (actor === "support") return "Flatmate support";
  if (actor === viewer) return "you";
  if (actor === "owner") return "the owner";
  if (actor === "applicant") return "the applicant";
  return "a former account";
}

/** "Submitted by you", "Rejected by the owner", "Under review by Flatmate support". */
export function timelineText(entry: ApplicationTimelineEntryDTO, viewer: TimelineViewer): string {
  return `${statusLabel(entry.to_status)} by ${actorLabel(entry.actor, viewer)}`;
}
