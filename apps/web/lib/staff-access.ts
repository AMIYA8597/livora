/**
 * Which parts of the admin console a signed-in user may open. Mirrors the API's role checks
 * (app/core/dependencies.py STAFF_ROLES and the require_roles lists on each route):
 * - admins and super admins: everything;
 * - moderators: the moderation queue and the applications panel (both allow STAFF_ROLES);
 *   platform stats, user management, listing approval and payment events stay admin-only.
 */
export type ConsoleTab = "stats" | "moderation" | "properties" | "applications" | "users" | "payments";

export const STAFF_ROLES = ["moderator", "admin", "super_admin"] as const;

const ADMIN_TABS: ConsoleTab[] = ["stats", "moderation", "properties", "applications", "users", "payments"];
const MODERATOR_TABS: ConsoleTab[] = ["moderation", "applications"];

export function isAdminRoles(roles: readonly string[]): boolean {
  return roles.includes("admin") || roles.includes("super_admin");
}

export function isStaffRoles(roles: readonly string[]): boolean {
  return roles.some((r) => (STAFF_ROLES as readonly string[]).includes(r));
}

/** The console tabs to show, in display order; empty means no access. */
export function consoleTabs(roles: readonly string[]): ConsoleTab[] {
  if (isAdminRoles(roles)) return ADMIN_TABS;
  if (roles.includes("moderator")) return MODERATOR_TABS;
  return [];
}
