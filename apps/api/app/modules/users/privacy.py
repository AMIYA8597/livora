"""
People's control over their data: download everything, and delete the account.

Export
    `export_user_data` returns the person's own records from every table that links to them,
    as JSON. Secrets (password and code hashes, push keys), other people's actions about
    them (who blocked or reported them) and internal vectors are left out.

Deletion (30-day grace)
    `request_deletion` (password confirmed) hides the account straight away: it is
    deactivated, so every token stops working and it drops out of search and matching;
    published listings are paused; renewing plans are cancelled; push stops. Signing in again
    before `purge_after` cancels it (`cancel_deletion`), unless staff deactivated the account.

    `purge_due_accounts` (hourly maintenance) erases accounts whose grace has passed:
      * personal records are deleted: profile, lifestyle, verifications, phone codes, roles,
        privacy settings, notifications, push, matches and likes, blocks, reports they filed,
        their applications and viewings, tenancies, group memberships, chat settings
      * their listings are deleted and anyone with an open application or upcoming viewing on
        them is notified
      * groups they created pass to the longest-standing other member, or are deleted
      * messages they sent stay in the other person's chat, shown as "Deleted user"; their
        attachments are deleted
      * payments and subscriptions stay for accounting, linked only to the anonymous row
      * the users row becomes a tombstone: no email, name, phone or usable password
      * their uploaded files are removed from storage
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy import Table, and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base
from app.core.exceptions import BadRequestException, ServiceUnavailableException
from app.core.security import verify_password
from app.modules.users.models import AccountDeletionRequest, User

logger = logging.getLogger("flatmate.privacy")

GRACE_DAYS = 30
EXPORT_FORMAT_VERSION = 1

# table -> columns that make a row "theirs". Only directions that describe the person's own
# activity: blocks *they* made, reports *they* filed, likes *they* gave.
EXPORT_TABLES: Dict[str, Tuple[str, ...]] = {
    "user_roles": ("user_id",),
    "role_requests": ("user_id",),
    "user_privacy_settings": ("user_id",),
    "profiles": ("user_id",),
    "lifestyle_profiles": ("user_id",),
    "user_dealbreakers": ("user_id",),
    "verifications": ("user_id",),
    "phone_verifications": ("user_id",),
    "notification_preferences": ("user_id",),
    "notifications": ("user_id",),
    "push_subscriptions": ("user_id",),
    "device_push_tokens": ("user_id",),
    "match_interactions": ("user_id",),
    "listing_interactions": ("user_id",),
    "mutual_matches": ("user_one_id", "user_two_id"),
    "user_blocks": ("user_id",),
    "moderation_reports": ("reporter_id",),
    "groups": ("creator_id",),
    "group_members": ("user_id",),
    "group_wishlist_items": ("added_by",),
    "properties": ("owner_id",),
    "pg_buildings": ("operator_id",),
    "existing_tenant_vacancies": ("posted_by_tenant_id",),
    "applications": ("applicant_id",),
    "application_status_events": ("actor_id",),
    "appointments": ("host_id", "applicant_id"),
    "tenant_memberships": ("tenant_id",),
    "subscriptions": ("user_id",),
    "payments": ("user_id",),
    "conversation_participants": ("user_id",),
    "conversation_preferences": ("user_id",),
    "conversation_read_cursors": ("user_id",),
    "messages": ("sender_id",),
    "attachments": ("uploader_id",),
}
# Never exported: credentials, one-time code hashes, push keys/endpoints/device tokens
# (capability URLs and tokens), internal search/ML columns.
EXCLUDED_COLUMNS = {
    "hashed_password", "code_hash", "subject_hash", "p256dh", "auth", "endpoint", "token",
    "idempotency_key", "embedding", "search_vector", "features",
}
EXCLUDED_TYPES = ("vector", "tsvector", "geography", "geometry")

OPEN_APPLICATION_STATUSES = ("submitted", "under_review", "reviewing", "accepted", "approved")
UPCOMING_APPOINTMENT_STATUSES = ("pending", "confirmed", "rescheduled")

# Erased outright when the grace period ends (single-column ownership).
PURGE_DELETE: Tuple[Tuple[str, str], ...] = (
    ("user_roles", "user_id"),
    ("role_requests", "user_id"),
    ("user_privacy_settings", "user_id"),
    ("profiles", "user_id"),
    ("lifestyle_profiles", "user_id"),
    ("user_dealbreakers", "user_id"),
    ("verifications", "user_id"),
    ("phone_verifications", "user_id"),
    ("notification_preferences", "user_id"),
    ("notifications", "user_id"),
    ("push_subscriptions", "user_id"),
    ("device_push_tokens", "user_id"),
    ("match_interactions", "user_id"),
    ("match_interactions", "target_user_id"),
    ("listing_interactions", "user_id"),
    ("mutual_matches", "user_one_id"),
    ("mutual_matches", "user_two_id"),
    ("user_blocks", "user_id"),
    ("user_blocks", "blocked_user_id"),
    ("moderation_reports", "reporter_id"),
    ("group_wishlist_items", "added_by"),
    ("group_members", "user_id"),
    ("applications", "applicant_id"),
    ("appointments", "applicant_id"),
    ("appointments", "host_id"),
    ("existing_tenant_vacancies", "posted_by_tenant_id"),
    ("tenant_memberships", "tenant_id"),
    ("conversation_preferences", "user_id"),
    ("conversation_read_cursors", "user_id"),
    ("attachments", "uploader_id"),
)
STORAGE_BUCKETS = ("avatars", "properties", "verification", "chat_attachments")


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


# --------------------------------------------------------------------------------- export

def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def _exportable_columns(table: Table) -> List[Any]:
    cols = []
    for col in table.columns:
        type_name = type(col.type).__name__.lower()
        if col.name in EXCLUDED_COLUMNS or any(t in type_name for t in EXCLUDED_TYPES):
            continue
        cols.append(col)
    return cols


async def export_user_data(db: AsyncSession, user: User) -> Dict[str, Any]:
    users = _table("users")
    account = (await db.execute(
        select(*_exportable_columns(users)).where(users.c.id == user.id)
    )).mappings().one()
    data: Dict[str, Any] = {
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": _jsonable(dict(account)),
    }
    for name, owner_cols in EXPORT_TABLES.items():
        table = Base.metadata.tables.get(name)
        if table is None:
            continue
        cols = _exportable_columns(table)
        cond = or_(*(table.c[c] == user.id for c in owner_cols))
        order = [table.c[c] for c in ("created_at", "sent_at", "joined_at", "submitted_at") if c in table.c][:1]
        rows = (await db.execute(select(*cols).where(cond).order_by(*order))).mappings().all()
        data[name] = [_jsonable(dict(r)) for r in rows]
    return data


# --------------------------------------------------------------------------------- requests

async def _pending(db: AsyncSession, user_id: UUID, lock: bool = False) -> Optional[AccountDeletionRequest]:
    query = select(AccountDeletionRequest).where(AccountDeletionRequest.user_id == user_id)
    if lock:
        query = query.with_for_update()
    return (await db.execute(query)).scalar_one_or_none()


async def _stop_renewals(db: AsyncSession, user: User) -> None:
    """Cancel plans that would charge again. A provider error stops the deletion: carrying on
    would leave someone paying for an account they deleted."""
    from app.modules.billing.razorpay import billing_enabled
    from app.modules.billing.service import BillingService
    from app.modules.subscriptions.models import Subscription

    renewing = (await db.execute(select(Subscription).where(
        Subscription.user_id == user.id,
        Subscription.provider_subscription_id.is_not(None),
        Subscription.status.in_(("created", "authenticated", "active", "pending")),
        Subscription.cancel_at_period_end.is_(False),
    ))).scalars().all()
    if not renewing:
        return
    if not billing_enabled():
        raise ServiceUnavailableException("Your plan can't be cancelled right now, so the account wasn't deleted. Try again later.")
    service = BillingService(db)
    for sub in renewing:
        await service.cancel(user, sub.id)


async def request_deletion(
    db: AsyncSession, user: User, password: str, background_tasks: Optional[BackgroundTasks] = None,
) -> AccountDeletionRequest:
    if not verify_password(password, user.hashed_password):
        raise BadRequestException("That password isn't right.")
    existing = await _pending(db, user.id)
    if existing is not None:
        return existing

    await _stop_renewals(db, user)

    properties = _table("properties")
    paused = (await db.execute(
        update(properties)
        .where(properties.c.owner_id == user.id, properties.c.listing_status == "published")
        .values(listing_status="paused")
        .returning(properties.c.id)
    )).scalars().all()
    await db.execute(delete(_table("push_subscriptions")).where(_table("push_subscriptions").c.user_id == user.id))
    await db.execute(delete(_table("device_push_tokens")).where(_table("device_push_tokens").c.user_id == user.id))

    now = datetime.now(timezone.utc)
    req = AccountDeletionRequest(
        user_id=user.id, requested_at=now, purge_after=now + timedelta(days=GRACE_DAYS),
        cancellable=True, paused_property_ids=[str(p) for p in paused],
    )
    db.add(req)
    user.is_active = False
    await db.commit()
    await db.refresh(req)
    logger.info("Account deletion requested", extra={"fields": {"user_id": str(user.id)}})
    await _close_sockets(user.id)

    if background_tasks is not None:
        from app.modules.notifications.emails import QueuedEmail, enqueue, idempotency_key, web_url

        await enqueue(db, background_tasks, [QueuedEmail(
            to=user.email,
            template="account_deletion_scheduled",
            context={
                "name": user.full_name,
                "purge_date": req.purge_after.strftime("%d %B %Y"),
                "sign_in_url": web_url("/login"),
            },
            idempotency_key=idempotency_key("account_deletion", user.id, req.requested_at.isoformat()),
        )])
    return req


async def _restore(db: AsyncSession, user: User, req: AccountDeletionRequest) -> None:
    ids = [uuid.UUID(p) for p in (req.paused_property_ids or [])]
    if ids:
        properties = _table("properties")
        await db.execute(
            update(properties)
            .where(properties.c.id.in_(ids), properties.c.owner_id == user.id, properties.c.listing_status == "paused")
            .values(listing_status="published")
        )
    await db.delete(req)
    user.is_active = True


async def cancel_deletion(db: AsyncSession, user: User) -> bool:
    """Called on sign-in with the right password. True when a pending deletion was cancelled."""
    if user.deleted_at is not None:
        return False
    req = await _pending(db, user.id, lock=True)
    if req is None or not req.cancellable or req.purge_after <= datetime.now(timezone.utc):
        return False
    await _restore(db, user, req)
    await db.commit()
    logger.info("Account deletion cancelled by sign-in", extra={"fields": {"user_id": str(user.id)}})
    return True


async def _close_sockets(user_id: UUID) -> None:
    """Live chat sockets of a disabled account close at once on every instance."""
    from app.modules.messaging.websocket import close_user_sockets_everywhere

    await close_user_sockets_everywhere(user_id)


async def on_staff_status_change(db: AsyncSession, user: User, is_active: bool) -> None:
    """Staff deactivation locks a pending deletion (signing in can't undo it); reactivation
    cancels it. The caller commits."""
    req = await _pending(db, user.id, lock=True)
    if req is None:
        return
    if is_active:
        await _restore(db, user, req)
    else:
        req.cancellable = False


# --------------------------------------------------------------------------------- erasure

async def _notify_listing_removed(db: AsyncSession, people: Dict[UUID, str]) -> None:
    from app.modules.notifications.service import NotificationService

    service = NotificationService(db)
    for person_id, title in people.items():
        try:
            await service.create_notification(
                user_id=person_id,
                title="A listing is no longer available",
                body=f"\"{title}\" was removed by its owner, so your application or viewing for it has been closed.",
                notification_type="application_status_change",
                link="/dashboard",
            )
        except Exception:  # noqa: BLE001 - erasure must not stop for a notification
            logger.warning("Couldn't notify a person about a removed listing", exc_info=True)


def _remove_files(prefixes: List[Tuple[str, str]]) -> None:
    from app.infrastructure.storage import get_storage
    from app.infrastructure.storage_buckets import get_bucket

    storage = get_storage()
    for logical, prefix in prefixes:
        spec = get_bucket(logical)
        if spec is None:
            continue
        try:
            storage.delete_prefix(spec.physical, prefix)
        except Exception as exc:  # noqa: BLE001 - logged; files sit under random names
            logger.warning("Couldn't remove %s files for an erased account: %s", logical, type(exc).__name__)


async def purge_account(db: AsyncSession, user_id: UUID) -> bool:
    """Erase one account (see module docstring). Idempotent. The caller holds the request lock."""
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        return False
    now = datetime.now(timezone.utc)
    properties, applications, appointments = _table("properties"), _table("applications"), _table("appointments")

    owned = (await db.execute(
        select(properties.c.id, properties.c.title).where(properties.c.owner_id == user_id)
    )).all()
    owned_ids = [p.id for p in owned]
    titles = {p.id: p.title for p in owned}
    affected: Dict[UUID, str] = {}
    if owned_ids:
        for person, prop in (await db.execute(
            select(applications.c.applicant_id, applications.c.property_id).where(
                applications.c.property_id.in_(owned_ids),
                applications.c.status.in_(OPEN_APPLICATION_STATUSES),
                applications.c.applicant_id != user_id,
            )
        )).all():
            affected[person] = titles[prop]
        for person, prop in (await db.execute(
            select(appointments.c.applicant_id, appointments.c.property_id).where(
                appointments.c.property_id.in_(owned_ids),
                appointments.c.status.in_(UPCOMING_APPOINTMENT_STATUSES),
                appointments.c.scheduled_at > now,
                appointments.c.applicant_id != user_id,
            )
        )).all():
            affected.setdefault(person, titles[prop])

    # Groups they created: hand over to the longest-standing other member, else delete.
    groups, members = _table("groups"), _table("group_members")
    for (group_id,) in (await db.execute(select(groups.c.id).where(groups.c.creator_id == user_id))).all():
        heir = (await db.execute(
            select(members.c.user_id)
            .where(members.c.group_id == group_id, members.c.user_id != user_id)
            .order_by(members.c.joined_at).limit(1)
        )).scalar_one_or_none()
        if heir is None:
            await db.execute(delete(groups).where(groups.c.id == group_id))
        else:
            await db.execute(update(groups).where(groups.c.id == group_id).values(creator_id=heir))
            await db.execute(update(members).where(members.c.group_id == group_id, members.c.user_id == heir)
                             .values(role="leader"))

    if owned_ids:
        await db.execute(delete(properties).where(properties.c.id.in_(owned_ids)))
    await db.execute(delete(_table("pg_buildings")).where(_table("pg_buildings").c.operator_id == user_id))
    for table_name, column in PURGE_DELETE:
        table = _table(table_name)
        await db.execute(delete(table).where(table.c[column] == user_id))
    participants = _table("conversation_participants")
    await db.execute(update(participants).where(participants.c.user_id == user_id, participants.c.is_active.is_(True))
                     .values(is_active=False, left_at=now))
    await db.execute(update(_table("beds")).where(_table("beds").c.current_occupant_id == user_id)
                     .values(current_occupant_id=None))
    await db.execute(delete(AccountDeletionRequest).where(AccountDeletionRequest.user_id == user_id))

    user.email = f"deleted+{user_id.hex}@deleted.invalid"
    user.full_name = "Deleted user"
    user.phone_number = None
    user.phone_verified_at = None
    user.hashed_password = "!" + secrets.token_hex(16)  # not a bcrypt hash: no password matches
    user.is_active = False
    user.is_verified = False
    user.deleted_at = now
    await db.commit()
    logger.info("Account erased", extra={"fields": {"user_id": str(user_id), "listings": len(owned_ids)}})
    await _close_sockets(user_id)

    prefixes = [(bucket, f"{user_id}/") for bucket in STORAGE_BUCKETS]
    prefixes += [("properties", f"prop_{pid}/") for pid in owned_ids]
    _remove_files(prefixes)
    await _notify_listing_removed(db, affected)
    return True


async def purge_due_accounts(session_factory: async_sessionmaker[AsyncSession], limit: int = 50) -> int:
    """Erase accounts whose grace period has passed. Safe to run concurrently (SKIP LOCKED)."""
    erased = 0
    for _ in range(limit):
        async with session_factory() as db:
            req = (await db.execute(
                select(AccountDeletionRequest)
                .where(and_(AccountDeletionRequest.purge_after <= datetime.now(timezone.utc)))
                .order_by(AccountDeletionRequest.purge_after)
                .limit(1)
                .with_for_update(skip_locked=True)
            )).scalar_one_or_none()
            if req is None:
                break
            try:
                if await purge_account(db, req.user_id):
                    erased += 1
            except Exception:
                await db.rollback()
                logger.exception("Account erasure failed; it will be retried")
                break
    return erased
