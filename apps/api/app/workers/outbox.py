"""
Transactional outbox dispatcher.

Producers insert `outbox_events` rows in the same database as the change that caused
them, so an event can never be lost once the request has been answered. The dispatcher:

  1. Claims due rows with `FOR UPDATE SKIP LOCKED` and pushes their `next_attempt_at`
     forward by a lease, then commits. Concurrent workers never pick up the same row,
     and no transaction stays open during network calls. If a worker dies mid-send, the
     lease expires and the row is retried.
  2. Runs the handler for each event type outside any transaction.
  3. On success marks the row `published` and scrubs its payload (reset links, message
     text). On failure it records the error and backs off exponentially. After
     MAX_ATTEMPTS the row is `failed` (a dead letter, kept for inspection and purged later).

Delivery is at-least-once: handlers must be idempotent (emails carry idempotency keys).

Handlers receive the dispatcher's session factory. Celery runs each task in a fresh event loop
with its own NullPool engine, so a handler must never use the API's pooled `AsyncSessionLocal`
(its connections belong to another loop).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.email import deliver_templated_email

logger = logging.getLogger("flatmate.outbox")

EMAIL_EVENT = "email.send"
MESSAGE_CREATED_EVENT = "message.created"

BATCH_SIZE = 50
MAX_ATTEMPTS = 8
LEASE = timedelta(minutes=5)
BASE_BACKOFF_SECONDS = 30
MAX_BACKOFF_SECONDS = 3600

SessionFactory = async_sessionmaker[AsyncSession]
Handler = Callable[[Dict[str, Any], SessionFactory], Awaitable[Dict[str, Any]]]


async def _handle_email(payload: Dict[str, Any], session_factory: SessionFactory) -> Dict[str, Any]:
    await deliver_templated_email(
        payload["to"], payload["template"], payload.get("context") or {}, payload.get("idempotency_key")
    )
    # Scrub: the context can hold single-use reset links and personal details. Keep only the
    # throttle key, which later sends check to avoid emailing the same person too often.
    scrubbed: Dict[str, Any] = {"template": payload["template"], "scrubbed": True}
    if payload.get("throttle_key"):
        scrubbed["throttle_key"] = payload["throttle_key"]
    return scrubbed


async def _handle_message_created(payload: Dict[str, Any], session_factory: SessionFactory) -> Dict[str, Any]:
    # Live delivery already happened over WebSocket during the request. This event is scheduled
    # CHAT_UNREAD_EMAIL_DELAY_MINUTES later: recipients who still haven't read the message get
    # an email. Imported here to avoid an import cycle (notifications -> outbox).
    from app.modules.notifications.emails import queue_unread_message_emails

    async with session_factory() as db:
        queued = await queue_unread_message_emails(db, payload)
    kept = {k: payload.get(k) for k in ("id", "conversation_id", "sender_id", "sent_at")}
    return {**kept, "emails_queued": queued}


async def _handle_embedding_refresh(payload: Dict[str, Any], session_factory: SessionFactory) -> Dict[str, Any]:
    from uuid import UUID

    from app.ml.indexing import refresh_embedding

    async with session_factory() as db:
        outcome = await refresh_embedding(db, payload["entity_type"], UUID(payload["entity_id"]))
    return {**payload, "outcome": outcome}


async def _handle_message_moderate(payload: Dict[str, Any], session_factory: SessionFactory) -> Dict[str, Any]:
    from uuid import UUID

    from app.ml.moderation_jobs import moderate_message

    return await moderate_message(session_factory, UUID(payload["message_id"]))


async def _handle_property_moderate(payload: Dict[str, Any], session_factory: SessionFactory) -> Dict[str, Any]:
    from uuid import UUID

    from app.ml.moderation_jobs import moderate_property

    return await moderate_property(session_factory, UUID(payload["property_id"]))


async def _handle_push(payload: Dict[str, Any], session_factory: SessionFactory) -> Dict[str, Any]:
    from app.modules.notifications.push import handle_push

    return await handle_push(payload, session_factory)


async def _handle_listing_geocode(payload: Dict[str, Any], session_factory: SessionFactory) -> Dict[str, Any]:
    from uuid import UUID

    from app.modules.locations.geocoding import geocode_listing

    return await geocode_listing(session_factory, UUID(payload["property_id"]))


HANDLERS: Dict[str, Handler] = {
    EMAIL_EVENT: _handle_email,
    MESSAGE_CREATED_EVENT: _handle_message_created,
    "embedding.refresh": _handle_embedding_refresh,
    "message.moderate": _handle_message_moderate,
    "property.moderate": _handle_property_moderate,
    "push.send": _handle_push,
    "listing.geocode": _handle_listing_geocode,
}


_kicks: "set[asyncio.Task[Any]]" = set()


def schedule_dispatch() -> None:
    """Fire-and-forget dispatch from the API process, for events that should run soon (e.g.
    moderation). The beat sweep is the safety net if this fails or the process exits."""
    from app.core.database import AsyncSessionLocal

    async def run() -> None:
        try:
            await dispatch_pending(AsyncSessionLocal)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Immediate outbox dispatch failed: %s", type(exc).__name__)

    try:
        task = asyncio.get_running_loop().create_task(run())
    except RuntimeError:
        return  # no running loop (e.g. a sync script): the sweep will pick it up
    _kicks.add(task)
    task.add_done_callback(_kicks.discard)


def backoff_for(attempt: int) -> timedelta:
    return timedelta(seconds=min(BASE_BACKOFF_SECONDS * 2 ** max(attempt - 1, 0), MAX_BACKOFF_SECONDS))


@dataclass
class DispatchResult:
    claimed: int = 0
    published: int = 0
    retried: int = 0
    dead_lettered: int = 0


CLAIM_SQL = text("""
    UPDATE outbox_events AS o
       SET next_attempt_at = now() + make_interval(secs => :lease_seconds)
      FROM (
            SELECT id FROM outbox_events
             WHERE status = 'pending' AND next_attempt_at <= now()
             ORDER BY next_attempt_at
             LIMIT :batch
             FOR UPDATE SKIP LOCKED
           ) AS due
     WHERE o.id = due.id
 RETURNING o.id, o.event_type, o.payload, o.retry_count
""")


async def dispatch_pending(session_factory: async_sessionmaker[AsyncSession], batch_size: int = BATCH_SIZE) -> DispatchResult:
    result = DispatchResult()
    async with session_factory() as session:
        rows = (await session.execute(
            CLAIM_SQL, {"lease_seconds": LEASE.total_seconds(), "batch": batch_size}
        )).mappings().all()
        await session.commit()
    result.claimed = len(rows)

    outcomes: List[Dict[str, Any]] = []
    for row in rows:
        handler = HANDLERS.get(row["event_type"])
        try:
            if handler is None:
                raise LookupError(f"No outbox handler for event type '{row['event_type']}'")
            scrubbed = await handler(dict(row["payload"]), session_factory)
            outcomes.append({"id": row["id"], "ok": True, "payload": scrubbed})
        except Exception as exc:  # noqa: BLE001 - every failure is recorded and retried
            attempt = row["retry_count"] + 1
            outcomes.append({
                "id": row["id"], "ok": False, "attempt": attempt,
                "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                "dead": attempt >= MAX_ATTEMPTS,
            })
            logger.warning("Outbox event %s (%s) failed attempt %s: %s",
                           row["id"], row["event_type"], attempt, type(exc).__name__)

    if not outcomes:
        return result

    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        for o in outcomes:
            if o["ok"]:
                await session.execute(text(
                    "UPDATE outbox_events SET status = 'published', processed_at = :now, "
                    "payload = CAST(:payload AS jsonb), last_error = NULL WHERE id = :id"
                ), {"now": now, "payload": _json(o["payload"]), "id": o["id"]})
                result.published += 1
            else:
                await session.execute(text(
                    "UPDATE outbox_events SET retry_count = :attempt, last_error = :error, "
                    "status = :status, next_attempt_at = :next_at, "
                    "processed_at = CASE WHEN :dead THEN :now ELSE processed_at END "
                    "WHERE id = :id"
                ), {
                    "attempt": o["attempt"], "error": o["error"], "id": o["id"], "now": now,
                    "status": "failed" if o["dead"] else "pending", "dead": o["dead"],
                    "next_at": now + backoff_for(o["attempt"]),
                })
                if o["dead"]:
                    result.dead_lettered += 1
                    logger.error("Outbox event %s dead-lettered after %s attempts", o["id"], o["attempt"])
                else:
                    result.retried += 1
        await session.commit()
    return result


def _json(value: Dict[str, Any]) -> str:
    import json
    return json.dumps(value, default=str)
