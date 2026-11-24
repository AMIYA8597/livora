"""Builds ranker training data and trains/registers the rankers: flatmates (likes/passes) and
listings (shown, then opened/saved/applied to)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.ml.ranker import NEGATIVE_ACTIONS, POSITIVE_ACTIONS, Example, TrainReport, train_and_register
from app.modules.matching.models import MatchInteraction
from app.modules.matching.service import MatchingService


async def build_examples(db: AsyncSession) -> List[Example]:
    """Likes/super-likes are positives, passes negatives ("save" is ambiguous and skipped).
    Uses the features snapshotted at decision time; older rows without one are recomputed
    from current profiles."""
    rows = (await db.execute(
        select(MatchInteraction).where(MatchInteraction.action.in_(POSITIVE_ACTIONS + NEGATIVE_ACTIONS))
    )).scalars().all()
    service = MatchingService(db)
    examples: List[Example] = []
    for row in rows:
        features = row.features or await service.pair_features(row.user_id, row.target_user_id)
        if not features:
            continue
        examples.append(Example(
            user_id=row.user_id, created_at=row.created_at, features=features,
            label=1 if row.action in POSITIVE_ACTIONS else 0,
        ))
    return examples


async def train_ranker(db: AsyncSession, dry_run: bool = False, min_rows: int | None = None) -> TrainReport:
    examples = await build_examples(db)
    return await train_and_register(
        db, examples, settings.RANKER_MIN_TRAINING_ROWS if min_rows is None else min_rows, dry_run=dry_run,
    )


async def build_listing_examples(db: AsyncSession) -> List[Example]:
    """One example per impression whose outcome is settled (older than LABEL_WINDOW): positive if
    the person opened, saved or applied to that listing within LABEL_WINDOW of being shown it.
    Features are the ones the ranking used at that moment."""
    from app.ml.listing_ranking import LABEL_WINDOW
    from app.ml.models import ListingInteraction
    from app.modules.applications.models import Application

    settled = datetime.now(timezone.utc) - LABEL_WINDOW
    shown = (await db.execute(select(ListingInteraction).where(
        ListingInteraction.action == "impression", ListingInteraction.features.is_not(None),
        ListingInteraction.created_at <= settled,
    ))).scalars().all()
    if not shown:
        return []
    users = list({row.user_id for row in shown})
    engaged: Dict[Tuple[UUID, UUID], List[datetime]] = {}
    acts = (await db.execute(select(ListingInteraction.user_id, ListingInteraction.property_id,
                                    ListingInteraction.created_at).where(
        ListingInteraction.user_id.in_(users), ListingInteraction.action.in_(("view", "save")),
    ))).all()
    apps = (await db.execute(select(Application.applicant_id, Application.property_id,
                                    Application.submitted_at).where(Application.applicant_id.in_(users)))).all()
    for uid, pid, at in [*acts, *apps]:
        engaged.setdefault((uid, pid), []).append(at)
    examples: List[Example] = []
    for row in shown:
        times = engaged.get((row.user_id, row.property_id), [])
        hit = any(row.created_at <= t <= row.created_at + LABEL_WINDOW for t in times)
        examples.append(Example(user_id=row.user_id, created_at=row.created_at,
                                features=dict(row.features), label=1 if hit else 0))
    return examples


async def train_listing_ranker(db: AsyncSession, dry_run: bool = False, min_rows: int | None = None) -> TrainReport:
    from app.ml.listing_ranking import LISTING_FEATURES, LISTING_MODEL_NAME, heuristic_score

    examples = await build_listing_examples(db)
    return await train_and_register(
        db, examples, settings.RANKER_MIN_TRAINING_ROWS if min_rows is None else min_rows, dry_run=dry_run,
        model_name=LISTING_MODEL_NAME, names=LISTING_FEATURES, baseline=heuristic_score,
    )
