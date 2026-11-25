"""
Who may hold which role, and who may hand it out.

- Anyone may sign up as one of SELF_SERVICE_ROLES.
- REQUESTABLE_ROLES are asked for from the profile and granted by an admin after a check
  (brokers: seekers trust a "no brokerage" platform, so a broker is someone we have vetted).
- Staff roles are only ever granted by staff: an admin may make moderators (and grant any
  non-staff role); only a super admin may make admins or super admins, or change one.
"""
from typing import FrozenSet, Iterable

SELF_SERVICE_ROLES: FrozenSet[str] = frozenset({"seeker", "tenant", "owner", "pg_operator"})
REQUESTABLE_ROLES: FrozenSet[str] = frozenset({"broker"})
STAFF_ROLES: FrozenSet[str] = frozenset({"moderator", "admin", "super_admin"})
SUPER_ADMIN_ONLY_ROLES: FrozenSet[str] = frozenset({"admin", "super_admin"})
ALL_ROLES: FrozenSet[str] = SELF_SERVICE_ROLES | REQUESTABLE_ROLES | STAFF_ROLES
# Who may put up listings and manage them (and the applications to them) from the dashboard.
LISTING_ROLES: FrozenSet[str] = frozenset({"owner", "pg_operator", "broker"})


def can_grant(actor_roles: Iterable[str], role: str) -> bool:
    """Whether someone holding `actor_roles` may grant or revoke `role`."""
    actor = set(actor_roles)
    if role not in ALL_ROLES:
        return False
    if "super_admin" in actor:
        return True
    if "admin" in actor:
        return role not in SUPER_ADMIN_ONLY_ROLES
    return False


def can_manage_account(actor_roles: Iterable[str], target_roles: Iterable[str]) -> bool:
    """Whether the actor may change another account's status or roles: admins and super admins
    are managed only by a super admin."""
    actor = set(actor_roles)
    if "super_admin" in actor:
        return True
    return "admin" in actor and not (set(target_roles) & SUPER_ADMIN_ONLY_ROLES)
