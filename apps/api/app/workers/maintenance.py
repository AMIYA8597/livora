"""
Periodic data-hygiene jobs. Each is a single set-based statement, safe to run
repeatedly and concurrently (idempotent), and returns the number of rows touched.
"""
from __future__ import annotations

import logging
from typing import Dict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger("flatmate.maintenance")

PUBLISHED_OUTBOX_RETENTION_DAYS = 7
FAILED_OUTBOX_RETENTION_DAYS = 30
PENDING_APPOINTMENT_GRACE_HOURS = 24

JOBS = {
    "purge_published_outbox": (
        "DELETE FROM outbox_events WHERE status = 'published' "
        "AND processed_at < now() - make_interval(days => :published_days)"
    ),
    "purge_failed_outbox": (
        "DELETE FROM outbox_events WHERE status = 'failed' "
        "AND processed_at < now() - make_interval(days => :failed_days)"
    ),
    # Razorpay subscriptions are kept current by webhooks (an "active" one whose period ended
    # is usually just awaiting its renewal event); only rows no provider manages, and finished
    # ones, are closed here. Access never depends on this: it is decided by expires_at.
    "expire_subscriptions": (
        "UPDATE subscriptions SET status = 'expired', updated_at = now() "
        "WHERE expires_at < now() AND ("
        "(provider_subscription_id IS NULL AND status IN ('active', 'cancelled')) "
        "OR status IN ('cancelled', 'completed', 'halted'))"
    ),
    # The notification centre shows recent activity; old read items are noise, and nothing
    # is kept for more than a year.
    "purge_old_notifications": (
        "DELETE FROM notifications WHERE (is_read AND created_at < now() - interval '90 days') "
        "OR created_at < now() - interval '365 days'"
    ),
    # Ranking signals (what people were shown, opened and saved) are only useful while recent.
    "purge_old_listing_interactions": (
        "DELETE FROM listing_interactions WHERE created_at < now() - interval '180 days'"
    ),
    "expire_unconfirmed_appointments": (
        "UPDATE appointments SET status = 'cancelled', "
        "cancellation_reason = 'Expired: not confirmed before the visit time', updated_at = now() "
        "WHERE status = 'pending' AND scheduled_at < now() - make_interval(hours => :grace_hours)"
    ),
}


async def run_maintenance(session_factory: async_sessionmaker[AsyncSession]) -> Dict[str, int]:
    params = {
        "published_days": PUBLISHED_OUTBOX_RETENTION_DAYS,
        "failed_days": FAILED_OUTBOX_RETENTION_DAYS,
        "grace_hours": PENDING_APPOINTMENT_GRACE_HOURS,
    }
    counts: Dict[str, int] = {}
    async with session_factory() as session:
        for name, sql in JOBS.items():
            res = await session.execute(text(sql), params)
            counts[name] = int(getattr(res, "rowcount", 0) or 0)
        await session.commit()
    # Accounts whose 30-day deletion grace has passed (see app/modules/users/privacy.py).
    from app.modules.users.privacy import purge_due_accounts

    counts["erase_deleted_accounts"] = await purge_due_accounts(session_factory)
    logger.info("Maintenance completed: %s", counts)
    return counts
