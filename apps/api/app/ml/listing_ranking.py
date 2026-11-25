"""
Per-person ranking of listings ("Recommended" order).

Every candidate listing gets explainable features for the person looking:

- relevance to the typed search (rank in the hybrid text+meaning search)
- distance from "near me"
- budget fit (against the cheapest way in: whole place, a room or a free bed) and move-in fit,
  from the person's profile
- trust and quality: verified owner, verified listing, photos, description, amenities, freshness,
  and how reliably the owner answers new enquiries within a day (smoothed)
- taste: similarity (embeddings) to listings they saved, applied to or opened, and to the rents
  and layouts of those listings; only when the person allows it (privacy setting)
- push-downs: listings they already applied to, open reports, and duplicates (a later copy of
  the same owner's listing, or photos already used by an earlier listing)

The order comes from a weighted score (HEURISTIC_WEIGHTS) until a learned model beats it: the
features shown with each impression are stored, and the weekly job trains a logistic ranker on
"shown, then opened/saved/applied to within LABEL_WINDOW" and activates it only if it wins on
held-out data (see app/ml/ranker.py). Paid featured listings stay first, as promised to owners,
unless they are reported or duplicates.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from uuid import UUID

import numpy as np
from geoalchemy2.shape import to_shape
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.embeddings import get_embedder
from app.ml.models import ContentEmbedding, ListingInteraction
from app.ml.ranker import active_ranker
from app.modules.applications.models import Application
from app.modules.locations.service import distance_km
from app.modules.moderation.models import ModerationReport
from app.modules.profiles.models import Profile
from app.modules.properties.models import Property
from app.modules.users.models import User, UserPrivacySetting

LISTING_MODEL_NAME = "listing_ranker"
LISTING_FEATURES: Tuple[str, ...] = (
    "text_match", "has_text",
    "distance_fit", "has_distance",
    "budget_fit", "has_budget",
    "move_in_fit", "has_move_in",
    "owner_verified", "listing_verified",
    "photo_quality", "description_quality", "amenity_richness", "freshness",
    "owner_response", "has_owner_response",
    "taste_similarity", "taste_rent", "taste_kind", "has_taste",
    "already_applied", "duplicate", "reported", "featured",
)
HEURISTIC_WEIGHTS: Dict[str, float] = {
    "text_match": 3.0, "distance_fit": 1.5, "budget_fit": 2.0, "move_in_fit": 0.8,
    "owner_verified": 0.5, "listing_verified": 0.5, "photo_quality": 0.8,
    "description_quality": 0.4, "amenity_richness": 0.2, "freshness": 0.8, "owner_response": 0.8,
    "taste_similarity": 1.2, "taste_rent": 0.6, "taste_kind": 0.4,
    "already_applied": -2.0, "duplicate": -4.0, "reported": -5.0,
}
CANDIDATE_LIMIT = 300          # listings scored per request (the best-matching/newest first)
TASTE_DAYS = 180
TASTE_WEIGHTS = {"apply": 1.0, "save": 1.0, "view": 0.3}
LABEL_WINDOW = timedelta(days=3)
IMPRESSION_DEDUPE = timedelta(hours=6)
VIEW_DEDUPE = timedelta(minutes=30)
RESPONSE_DAYS = 90
# Profiles start with these placeholder budgets; they say nothing about the person.
PLACEHOLDER_BUDGET = (500, 2500)


def heuristic_score(features: Dict[str, float]) -> float:
    return sum(w * features.get(k, 0.0) for k, w in HEURISTIC_WEIGHTS.items())


# ---------------------------------------------------------------- the person

@dataclass
class Viewer:
    user_id: Optional[UUID] = None
    personalized: bool = False          # may use (and record) their activity
    budget: Optional[Tuple[int, int]] = None
    move_in: Optional[date] = None
    applied: Set[UUID] = field(default_factory=set)
    taste_vector: Optional[np.ndarray] = None
    taste_rent: Optional[float] = None
    taste_kinds: Dict[str, float] = field(default_factory=dict)

    @property
    def has_taste(self) -> bool:
        return self.taste_vector is not None or self.taste_rent is not None


def _unit(v: np.ndarray) -> Optional[np.ndarray]:
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else None


async def _vectors(db: AsyncSession, ids: Iterable[UUID]) -> Dict[UUID, np.ndarray]:
    ids = list(set(ids))
    if not ids:
        return {}
    model_id = get_embedder().model_id
    rows = (await db.execute(select(ContentEmbedding.entity_id, ContentEmbedding.embedding).where(
        ContentEmbedding.entity_type == "property", ContentEmbedding.model == model_id,
        ContentEmbedding.entity_id.in_(ids),
    ))).all()
    out: Dict[UUID, np.ndarray] = {}
    for entity_id, emb in rows:
        unit = _unit(np.asarray(emb, dtype=float))
        if unit is not None:
            out[entity_id] = unit
    return out


async def load_viewer(db: AsyncSession, user_id: Optional[UUID]) -> Viewer:
    if user_id is None:
        return Viewer()
    viewer = Viewer(user_id=user_id)
    profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one_or_none()
    if profile is not None:
        if (profile.budget_min, profile.budget_max) != PLACEHOLDER_BUDGET and profile.budget_max > 0:
            viewer.budget = (max(0, profile.budget_min), profile.budget_max)
        viewer.move_in = profile.move_in_date
    since = datetime.now(timezone.utc) - timedelta(days=TASTE_DAYS)
    applications = (await db.execute(select(Application.property_id).where(
        Application.applicant_id == user_id, Application.submitted_at >= since,
    ))).scalars().all()
    viewer.applied = set(applications)

    allowed = (await db.execute(select(UserPrivacySetting.personalized_ranking).where(
        UserPrivacySetting.user_id == user_id))).scalar_one_or_none()
    viewer.personalized = allowed is not False  # no settings row yet = the default (on)
    if not viewer.personalized:
        return viewer

    weights: Dict[UUID, float] = {pid: TASTE_WEIGHTS["apply"] for pid in viewer.applied}
    rows = (await db.execute(
        select(ListingInteraction.property_id, ListingInteraction.action, ListingInteraction.created_at)
        .where(ListingInteraction.user_id == user_id, ListingInteraction.created_at >= since,
               ListingInteraction.action.in_(("view", "save", "unsave")))
        .order_by(ListingInteraction.created_at)
    )).all()
    saved: Dict[UUID, bool] = {}
    for pid, action, _ in rows:
        if action == "view":
            weights[pid] = max(weights.get(pid, 0.0), TASTE_WEIGHTS["view"])
        else:
            saved[pid] = action == "save"  # the latest save/unsave wins
    for pid, is_saved in saved.items():
        if is_saved:
            weights[pid] = max(weights.get(pid, 0.0), TASTE_WEIGHTS["save"])
    if not weights:
        return viewer

    vectors = await _vectors(db, weights)
    if vectors:
        viewer.taste_vector = _unit(np.sum([weights[pid] * v for pid, v in vectors.items()], axis=0))
    liked = (await db.execute(select(Property.id, Property.monthly_rent, Property.configuration).where(
        Property.id.in_(list(weights))))).all()
    if liked:
        total = sum(weights[pid] for pid, _, _ in liked)
        rents = sorted((float(rent), weights[pid]) for pid, rent, _ in liked)
        acc = 0.0
        for rent, w in rents:  # weighted median
            acc += w
            if acc >= total / 2:
                viewer.taste_rent = rent
                break
        for pid, _, config in liked:
            viewer.taste_kinds[config] = viewer.taste_kinds.get(config, 0.0) + weights[pid] / total
    return viewer


# ---------------------------------------------------------------- the listings

def cheapest_way_in(prop: Property) -> float:
    rents = [float(prop.monthly_rent)]
    for room in prop.rooms or []:
        if room.is_available and room.room_rent:
            rents.append(float(room.room_rent))
        for bed in room.beds or []:
            if not bed.is_occupied and bed.monthly_rent:
                rents.append(float(bed.monthly_rent))
    return min(r for r in rents if r > 0) if any(r > 0 for r in rents) else float(prop.monthly_rent)


def budget_fit(rent: float, budget: Tuple[int, int]) -> float:
    low, high = budget
    if low <= rent <= high:
        return 1.0
    if rent > high:
        return max(0.0, 1.0 - (rent - high) / (0.5 * high)) if high > 0 else 0.0
    return max(0.5, 1.0 - (low - rent) / low) if low > 0 else 1.0  # cheaper is a smaller miss


def move_in_fit(available_from: Optional[date], move_in: date) -> float:
    if available_from is None or available_from <= move_in:
        return 1.0
    return max(0.0, 1.0 - (available_from - move_in).days / 45.0)


def _norm_address(s: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in s).split())


async def _duplicates(db: AsyncSession, props: Sequence[Property]) -> Set[UUID]:
    """Listings with an earlier twin: the same owner's same place (address, layout, rent), or
    photos an earlier listing already uses."""
    dupes: Set[UUID] = set()
    live = (Property.is_active.is_(True), Property.listing_status == "published")
    owners = list({p.owner_id for p in props})
    siblings = (await db.execute(select(
        Property.id, Property.owner_id, Property.address_display, Property.configuration,
        Property.monthly_rent, Property.created_at,
    ).where(Property.owner_id.in_(owners), *live))).all()
    first: Dict[tuple, Tuple[datetime, UUID]] = {}
    for pid, owner, addr, config, rent, created in siblings:
        key = (owner, _norm_address(addr), config, float(rent))
        if key not in first or (created, pid) < first[key]:
            first[key] = (created, pid)
    for p in props:
        key = (p.owner_id, _norm_address(p.address_display), p.configuration, float(p.monthly_rent))
        if key in first and first[key][1] != p.id:
            dupes.add(p.id)

    images = sorted({img for p in props for img in (p.images or [])})
    if images:
        rows = (await db.execute(select(Property.id, Property.created_at, Property.images).where(
            Property.images.overlap(images), *live))).all()
        earliest: Dict[str, Tuple[datetime, UUID]] = {}
        for pid, created, imgs in rows:
            for img in imgs or []:
                if img not in earliest or (created, pid) < earliest[img]:
                    earliest[img] = (created, pid)
        for p in props:
            if any(earliest.get(img, (None, p.id))[1] != p.id for img in p.images or []):
                dupes.add(p.id)
    return dupes


async def _open_reports(db: AsyncSession, ids: Sequence[UUID]) -> Dict[UUID, int]:
    rows = (await db.execute(select(ModerationReport.target_id, func.count()).where(
        ModerationReport.target_type == "property", ModerationReport.target_id.in_(list(ids)),
        ModerationReport.status.in_(("open", "under_investigation")),
    ).group_by(ModerationReport.target_id))).all()
    return {tid: n for tid, n in rows}


async def owner_response_rates(db: AsyncSession, owner_ids: Sequence[UUID]) -> Dict[UUID, Tuple[int, int]]:
    """Per owner: (conversations someone else started in the last RESPONSE_DAYS, how many the
    owner answered within 24 hours)."""
    if not owner_ids:
        return {}
    rows = (await db.execute(text(
        """
        WITH firsts AS (
            SELECT cp.user_id AS owner_id, m.conversation_id, min(m.sent_at) AS asked_at
            FROM conversation_participants cp
            JOIN messages m ON m.conversation_id = cp.conversation_id
                           AND m.sender_id <> cp.user_id AND NOT m.is_deleted
                           AND m.message_type <> 'system'
            WHERE cp.user_id = ANY(:owners) AND m.sent_at > now() - make_interval(days => :days)
            GROUP BY cp.user_id, m.conversation_id
        )
        SELECT f.owner_id, count(*) AS asked,
               count(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM messages r
                   WHERE r.conversation_id = f.conversation_id AND r.sender_id = f.owner_id
                     AND r.message_type <> 'system'
                     AND r.sent_at > f.asked_at AND r.sent_at <= f.asked_at + interval '24 hours'
               )) AS answered
        FROM firsts f GROUP BY f.owner_id
        """
    ), {"owners": list(owner_ids), "days": RESPONSE_DAYS})).all()
    return {owner: (int(asked), int(answered)) for owner, asked, answered in rows}


@dataclass
class Ranked:
    prop: Property
    features: Dict[str, float]
    score: float
    reasons: List[str]
    pinned: bool  # featured, and not reported or a duplicate


def _reasons(f: Dict[str, float], age_days: float, km: Optional[float], asked: int) -> List[str]:
    picks: List[Tuple[float, str]] = []
    if f["has_budget"] and f["budget_fit"] >= 1.0:
        picks.append((2.0, "Within your budget"))
    if f["has_move_in"] and f["move_in_fit"] >= 1.0:
        picks.append((0.8, "Free by your move-in date"))
    if f["has_taste"] and f["taste_similarity"] >= 0.6:
        picks.append((1.2, "Like places you saved"))
    if km is not None and km < 2:
        picks.append((1.5, "Close to you"))
    if asked >= 3 and f["owner_response"] >= 0.7:
        picks.append((0.8, "Owner replies within a day"))
    if f["owner_verified"]:
        picks.append((0.5, "Verified owner"))
    if age_days < 7:
        picks.append((0.4, "New this week"))
    return [text_ for _, text_ in sorted(picks, key=lambda p: -p[0])[:2]]


async def rank_listings(
    db: AsyncSession, props: Sequence[Property], viewer: Viewer, *,
    text_ranks: Optional[Dict[UUID, int]] = None, near: Optional[Tuple[float, float]] = None,
    radius_km: float = 10.0,
) -> List[Ranked]:
    if not props:
        return []
    ids = [p.id for p in props]
    owners = list({p.owner_id for p in props})
    verified: Dict[object, bool] = {
        row[0]: bool(row[1])
        for row in (await db.execute(select(User.id, User.is_verified).where(User.id.in_(owners)))).all()
    }
    reports = await _open_reports(db, ids)
    responses = await owner_response_rates(db, owners)
    dupes = await _duplicates(db, props)
    vectors = await _vectors(db, ids) if viewer.taste_vector is not None else {}
    model = await active_ranker(db, LISTING_MODEL_NAME)
    now = datetime.now(timezone.utc)

    ranked: List[Ranked] = []
    for p in props:
        f = dict.fromkeys(LISTING_FEATURES, 0.0)
        if text_ranks is not None:
            f["has_text"] = 1.0
            rank = text_ranks.get(p.id)
            f["text_match"] = 1.0 / (1.0 + rank / 5.0) if rank is not None else 0.0
        km = None
        if near is not None:
            point = to_shape(p.location)
            km = distance_km(near[0], near[1], point.y, point.x)
            f["has_distance"] = 1.0
            f["distance_fit"] = math.exp(-km / max(radius_km / 2.0, 1.0))
        if viewer.budget:
            f["has_budget"] = 1.0
            f["budget_fit"] = budget_fit(cheapest_way_in(p), viewer.budget)
        if viewer.move_in:
            f["has_move_in"] = 1.0
            f["move_in_fit"] = move_in_fit(p.available_from, viewer.move_in)
        f["owner_verified"] = 1.0 if verified.get(p.owner_id) else 0.0
        f["listing_verified"] = 1.0 if p.is_verified else 0.0
        f["photo_quality"] = min(len(p.images or []), 6) / 6.0
        f["description_quality"] = min(len((p.description or "").strip()), 600) / 600.0
        f["amenity_richness"] = min(len(p.amenities or []), 8) / 8.0
        created = p.created_at if p.created_at.tzinfo else p.created_at.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - created).total_seconds() / 86400.0)
        f["freshness"] = math.exp(-age_days / 21.0)
        asked, answered = responses.get(p.owner_id, (0, 0))
        f["has_owner_response"] = 1.0 if asked else 0.0
        f["owner_response"] = (answered + 1) / (asked + 2)  # 0.5 when unknown
        if viewer.has_taste:
            f["has_taste"] = 1.0
            vec = vectors.get(p.id)
            if viewer.taste_vector is not None and vec is not None:
                f["taste_similarity"] = max(0.0, float(vec @ viewer.taste_vector))
            if viewer.taste_rent:
                f["taste_rent"] = math.exp(-2.0 * abs(math.log(max(cheapest_way_in(p), 1.0) / viewer.taste_rent)))
            f["taste_kind"] = viewer.taste_kinds.get(p.configuration, 0.0)
        f["already_applied"] = 1.0 if p.id in viewer.applied else 0.0
        f["duplicate"] = 1.0 if p.id in dupes else 0.0
        f["reported"] = 1.0 if reports.get(p.id) else 0.0  # any open report: possible scam
        featured_until = p.featured_until
        is_featured = bool(featured_until and (featured_until if featured_until.tzinfo else featured_until.replace(tzinfo=timezone.utc)) > now)
        f["featured"] = 1.0 if is_featured else 0.0

        score = model.score(f) if model is not None else heuristic_score(f)
        pinned = is_featured and not f["duplicate"] and not f["reported"]
        ranked.append(Ranked(p, f, score, _reasons(f, age_days, km, asked), pinned))

    ranked.sort(key=lambda r: (not r.pinned, -r.score, -r.prop.created_at.timestamp(), str(r.prop.id)))
    return ranked


# ---------------------------------------------------------------- recording

async def record_impressions(db: AsyncSession, viewer: Viewer, page: Sequence[Ranked], offset: int) -> int:
    """Store what this person was shown (and the features) so the ranker can learn. Skips
    listings already recorded for them in the last IMPRESSION_DEDUPE. Caller commits."""
    if not viewer.personalized or viewer.user_id is None or not page:
        return 0
    since = datetime.now(timezone.utc) - IMPRESSION_DEDUPE
    recent = set((await db.execute(select(ListingInteraction.property_id).where(
        ListingInteraction.user_id == viewer.user_id, ListingInteraction.action == "impression",
        ListingInteraction.created_at >= since,
        ListingInteraction.property_id.in_([r.prop.id for r in page]),
    ))).scalars().all())
    added = 0
    for i, r in enumerate(page):
        if r.prop.id in recent:
            continue
        db.add(ListingInteraction(user_id=viewer.user_id, property_id=r.prop.id, action="impression",
                                  position=offset + i, features=r.features))
        added += 1
    return added


async def record_action(db: AsyncSession, user_id: UUID, property_id: UUID, action: str,
                        position: Optional[int] = None) -> bool:
    """view / save / unsave from the person. Returns False when not recorded (they opted out, or
    the same view moments ago). Commits."""
    allowed = (await db.execute(select(UserPrivacySetting.personalized_ranking).where(
        UserPrivacySetting.user_id == user_id))).scalar_one_or_none()
    if allowed is False:
        return False
    if action == "view":
        since = datetime.now(timezone.utc) - VIEW_DEDUPE
        seen = (await db.execute(select(ListingInteraction.id).where(
            ListingInteraction.user_id == user_id, ListingInteraction.property_id == property_id,
            ListingInteraction.action == "view", ListingInteraction.created_at >= since,
        ).limit(1))).scalar_one_or_none()
        if seen is not None:
            return False
    db.add(ListingInteraction(user_id=user_id, property_id=property_id, action=action, position=position))
    await db.commit()
    return True
