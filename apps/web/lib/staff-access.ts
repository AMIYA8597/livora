/**
 * Which parts of the admin console a signed-in user may open, and which roles they may hand out.
 * Mirrors the API (app/core/roles.py and the require_roles lists on each route); the API is
 * the real check, this only decides what to show:
 * - admins and super admins: everything;
 * - moderators: the moderation queue and the applications panel (both allow STAFF_ROLES);
 *   platform stats, listing approval, user management, role requests and payment events stay
 *   admin-only.
 */
export type ConsoleTab = "stats" | "moderation" | "properties" | "applications" | "users" | "roles" | "payments";

export const STAFF_ROLES = ["moderator", "admin", "super_admin"] as const;

/** Every role the API knows, in the order the console lists them. */
export const ALL_ROLES = [
  "seeker",
  "tenant",
  "owner",
  "pg_operator",
  "broker",
  "moderator",
  "admin",
  "super_admin",
] as const;

/** Roles only a super admin can grant, and accounts only a super admin can change. */
const SUPER_ADMIN_ONLY = ["admin", "super_admin"];

const ADMIN_TABS: ConsoleTab[] = ["stats", "moderation", "properties", "applications", "users", "roles", "payments"];
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

/** May this staff member change that account (status or roles)? Admins can't touch other admins. */
export function canManageAccount(actorRoles: readonly string[], targetRoles: readonly string[]): boolean {
  if (actorRoles.includes("super_admin")) return true;
  if (!actorRoles.includes("admin")) return false;
  return !targetRoles.some((r) => SUPER_ADMIN_ONLY.includes(r));
}

/** May this staff member grant (or remove) that role? */
export function canGrantRole(actorRoles: readonly string[], role: string): boolean {
  if (!(ALL_ROLES as readonly string[]).includes(role)) return false;
  if (actorRoles.includes("super_admin")) return true;
  return actorRoles.includes("admin") && !SUPER_ADMIN_ONLY.includes(role);
}

/** Roles the actor could add to this account: ones it lacks and the actor may grant. */
export function grantableRoles(actorRoles: readonly string[], targetRoles: readonly string[]): string[] {
  return ALL_ROLES.filter((r) => !targetRoles.includes(r) && canGrantRole(actorRoles, r));
}

/**
 * Roles the actor could remove from this account. Never the primary role (the account's main
 * type), and never the actor's own staff role from their own account: that's a lockout.
 */
export function removableRoles(
  actorRoles: readonly string[],
  target: { roles: readonly string[]; role: string; isSelf: boolean },
): string[] {
  return target.roles.filter(
    (r) =>
      r !== target.role &&
      canGrantRole(actorRoles, r) &&
      !(target.isSelf && (STAFF_ROLES as readonly string[]).includes(r)),
  );
}
