/**
 * Broker access: a member asks from their profile, an admin approves or declines with a reason.
 * Shared by the profile card and the admin console; the API (users/role_requests.py) decides.
 */
export type RoleRequestStatus = "pending" | "approved" | "declined";

export interface RoleRequest {
  id: string;
  role: string;
  status: RoleRequestStatus;
  note: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
}

/** Matches the API's limit on both the request note and the decision note. */
export const NOTE_MAX = 500;

const ROLE_LABELS: Record<string, string> = {
  seeker: "Seeker",
  tenant: "Tenant",
  owner: "Owner",
  pg_operator: "PG operator",
  broker: "Broker",
  moderator: "Moderator",
  admin: "Admin",
  super_admin: "Super admin",
};

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role.replace(/_/g, " ");
}

export function requestTone(status: string): "warning" | "success" | "danger" | "default" {
  if (status === "pending") return "warning";
  if (status === "approved") return "success";
  if (status === "declined") return "danger";
  return "default";
}

export function requestStatusLabel(status: string): string {
  if (status === "pending") return "Waiting for review";
  if (status === "approved") return "Approved";
  if (status === "declined") return "Not approved";
  return status;
}

export type BrokerAccess =
  | { state: "broker" }
  | { state: "pending"; request: RoleRequest }
  | { state: "declined"; request: RoleRequest }
  | { state: "none" };

/**
 * What the profile card shows. A held role wins (a broker sees "you're a broker" even if an old
 * request was declined); otherwise the newest request decides. A declined member may ask again.
 */
export function brokerAccess(roles: readonly string[], requests: readonly RoleRequest[]): BrokerAccess {
  if (roles.includes("broker")) return { state: "broker" };
  const latest = requests
    .filter((r) => r.role === "broker")
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  if (latest?.status === "pending") return { state: "pending", request: latest };
  if (latest?.status === "declined") return { state: "declined", request: latest };
  return { state: "none" };
}

/** A decline must say why (the member sees it); an approval note is optional. */
export function decisionProblem(approve: boolean, note: string): string | null {
  const text = note.trim();
  if (!approve && !text) return "Say why, so the member knows what to fix.";
  if (text.length > NOTE_MAX) return `Keep it under ${NOTE_MAX} characters.`;
  return null;
}
