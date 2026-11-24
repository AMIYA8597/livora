"""Builds ranker training data from match interactions and trains/registers the ranker."""
from __future__ import annotations

from typing import List

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
