"""
Per-person listing ranking ("Recommended") against a real database: budget and move-in fit,
trust and quality, duplicates and reports pushed down, featured listings kept first, taste from
saves, what gets recorded (and not, when the person opts out), server-side sorting across pages,
owner response rates and building training examples.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.ml.listing_ranking import (
    LISTING_FEATURES, budget_fit, cheapest_way_in, heuristic_score, move_in_fit, owner_response_rates,
)
from app.ml.models import ListingInteraction
from app.ml.training import build_listing_examples, train_listing_ranker
from app.modules.messaging.models import Conversation, ConversationParticipant, Message, OutboxEvent
from app.modules.moderation.models import ModerationReport
from app.modules.profiles.models import Profile
from app.modules.properties.models import Property
from app.modules.properties.schemas import PropertyCreate
from app.modules.properties.service import PropertyService
from app.modules.users.models import User, UserPrivacySetting
from app.modules.users.privacy import EXPORT_TABLES, PURGE_DELETE

API = settings.API_V1_PREFIX
KOHIMA = (25.6751, 94.1086)


def auth(user_id, role="seeker"):
    return {"Authorization": f"Bearer {create_access_token(subject=str(user_id), roles=[role])}"}


# ---------------------------------------------------------------- pure parts

def test_fits_and_weights():
    assert budget_fit(12000, (10000, 16000)) == 1.0
    assert budget_fit(20000, (10000, 16000)) == pytest.approx(0.5)   # 25% over a 16k budget
    assert budget_fit(24000, (10000, 16000)) == 0.0                  # 50% over: no fit
    assert budget_fit(8000, (10000, 16000)) == pytest.approx(0.8)    # cheaper is a smaller miss
    today = date.today()
    assert move_in_fit(today, today + timedelta(days=5)) == 1.0
    assert move_in_fit(today + timedelta(days=45), today) == 0.0
    assert move_in_fit(None, today) == 1.0
    room = SimpleNamespace(is_available=True, room_rent=Decimal("9000"),
                           beds=[SimpleNamespace(is_occupied=False, monthly_rent=Decimal("6500")),
                                 SimpleNamespace(is_occupied=True, monthly_rent=Decimal("5000"))])
    assert cheapest_way_in(SimpleNamespace(monthly_rent=Decimal("30000"), rooms=[room])) == 6500.0
    clean = dict.fromkeys(LISTING_FEATURES, 0.0)
    assert heuristic_score({**clean, "duplicate": 1.0}) < heuristic_score(clean)
    assert heuristic_score({**clean, "reported": 1.0}) < heuristic_score({**clean, "duplicate": 1.0})
    assert heuristic_score({**clean, "budget_fit": 1.0}) > heuristic_score(clean)


def test_new_table_is_exported_and_erased_with_the_account():
    assert EXPORT_TABLES["listing_interactions"] == ("user_id",)
    assert ("listing_interactions", "user_id") in PURGE_DELETE


# ---------------------------------------------------------------- a small marketplace

def _listing(tag, title, rent, config="1BHK", images=(), description="Room.", address=None):
    return PropertyCreate(
        title=title, description=description, property_category="apartment", configuration=config,
        latitude=KOHIMA[0], longitude=KOHIMA[1], address_display=address or f"{tag} Colony, Kohima",
        address_exact="1 Test Road", city="Kohima", state="Nagaland", postal_code="797001",
        monthly_rent=Decimal(rent), max_capacity=2, available_from=date.today(), currency="INR",
        images=list(images),
    )


@pytest.fixture
async def market():
    tag = f"Rank{uuid4().hex[:8]}"
    seeker, verified_owner, other_owner, reporter = uuid4(), uuid4(), uuid4(), uuid4()
    async with AsyncSessionLocal() as s:
        s.add_all([
            User(id=seeker, email=f"{tag}-s@example.com", hashed_password="x", full_name="Sia Seeker", role="seeker"),
            User(id=verified_owner, email=f"{tag}-a@example.com", hashed_password="x", full_name="Asha Owner",
                 role="owner", is_verified=True),
            User(id=other_owner, email=f"{tag}-b@example.com", hashed_password="x", full_name="Bo Owner", role="owner"),
            User(id=reporter, email=f"{tag}-r@example.com", hashed_password="x", full_name="Ravi Reporter", role="seeker"),
        ])
        await s.flush()
        s.add(Profile(user_id=seeker, display_name="Sia", budget_min=10000, budget_max=16000,
                      move_in_date=date.today() + timedelta(days=10)))
        await s.commit()

    long_text = "Bright, quiet room with a balcony, fast wifi and a short walk to the market. " * 8
    photos = [f"https://img.example/{tag}/{i}.jpg" for i in range(6)]
    ids = {}

    async def create(name, owner, data):
        async with AsyncSessionLocal() as s:
            ids[name] = (await PropertyService(s).create(owner, data))["id"]

    await create("best", verified_owner, _listing(tag, f"{tag} best", "14000", images=photos, description=long_text))
    await create("pricey", other_owner, _listing(tag, f"{tag} pricey", "30000", config="2BHK",
                                                 address=f"{tag} Hills, Kohima"))
    await create("copy", verified_owner, _listing(tag, f"{tag} copy", "14000", images=[], description=long_text))
    await create("stolen_photos", other_owner, _listing(tag, f"{tag} photos", "14000", images=photos[:1],
                                                        address=f"{tag} Market, Kohima"))
    await create("reported", other_owner, _listing(tag, f"{tag} reported", "13000",
                                                   address=f"{tag} Lane, Kohima"))
    async with AsyncSessionLocal() as s:
        s.add(ModerationReport(reporter_id=reporter, target_type="property", target_id=ids["reported"],
                               reason="scam", status="open"))
        await s.commit()

    yield SimpleNamespace(tag=tag, seeker=seeker, owners=(verified_owner, other_owner), ids=ids)

    async with AsyncSessionLocal() as s:
        pids = list(ids.values())
        await s.execute(delete(ModerationReport).where(ModerationReport.target_id.in_(pids)))
        await s.execute(delete(OutboxEvent).where(OutboxEvent.payload["property_id"].astext.in_([str(p) for p in pids])))
        # Listing creation also queues embedding refreshes, keyed by entity_id: left behind, they
        # crowd other tests' events out of the outbox dispatcher's batch.
        await s.execute(delete(OutboxEvent).where(OutboxEvent.payload["entity_id"].astext.in_([str(p) for p in pids])))
        await s.execute(delete(Property).where(Property.id.in_(pids)))
        await s.execute(delete(User).where(User.id.in_([seeker, verified_owner, other_owner, reporter])))
        await s.commit()


async def _get(client, m, headers=None, **params):
    res = await client.get(f"{API}/properties", params={"locality": m.tag, "limit": 50, **params}, headers=headers or {})
    assert res.status_code == 200, res.text
    return res.json()


def _names(m, rows):
    by_id = {str(v): k for k, v in m.ids.items()}
    return [by_id[r["id"]] for r in rows if r["id"] in by_id]


async def _impressions(user_id):
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(ListingInteraction).where(
            ListingInteraction.user_id == user_id, ListingInteraction.action == "impression"
        ).order_by(ListingInteraction.position))).scalars().all()


async def test_recommended_order_for_a_seeker(async_client, market):
    rows = await _get(async_client, market, auth(market.seeker), sort="recommended")
    order = _names(market, rows)
    assert order[0] == "best"
    # The copies and the reported listing sink below the honest, in-budget listings.
    assert set(order[-3:]) == {"copy", "stolen_photos", "reported"}
    assert order[-1] == "reported"
    best = next(r for r in rows if r["id"] == str(market.ids["best"]))
    assert "Within your budget" in best["match_reasons"]
    assert len(best["match_reasons"]) <= 2

    shown = await _impressions(market.seeker)
    assert [str(i.property_id) for i in shown] == [r["id"] for r in rows][:len(shown)]
    assert shown[0].position == 0 and set(shown[0].features) == set(LISTING_FEATURES)
    assert shown[0].features["has_budget"] == 1.0
    # Shown again within hours: not recorded twice.
    await _get(async_client, market, auth(market.seeker), sort="recommended")
    assert len(await _impressions(market.seeker)) == len(shown)


async def test_featured_listings_stay_first_unless_reported(async_client, market):
    async with AsyncSessionLocal() as s:
        soon = datetime.now(timezone.utc) + timedelta(days=7)
        await s.execute(update(Property).where(Property.id.in_([market.ids["pricey"], market.ids["reported"]]))
                        .values(featured_until=soon))
        await s.commit()
    order = _names(market, await _get(async_client, market, auth(market.seeker), sort="recommended"))
    assert order[0] == "pricey"            # paid placement kept, as promised to owners
    assert order[-1] == "reported"         # but never for a reported listing


async def test_anonymous_visitors_get_a_ranking_but_nothing_is_recorded(async_client, market):
    rows = await _get(async_client, market, sort="recommended")
    assert _names(market, rows)[0] == "best"
    assert all("Within your budget" not in r["match_reasons"] for r in rows)
    async with AsyncSessionLocal() as s:
        n = (await s.execute(select(ListingInteraction).where(
            ListingInteraction.property_id.in_(list(market.ids.values()))))).scalars().all()
    assert n == []


async def test_saves_shape_taste_and_opting_out_stops_recording(async_client, market):
    h = auth(market.seeker)
    url = f"{API}/properties/{market.ids['pricey']}/interactions"
    assert (await async_client.post(url, json={"action": "save"}, headers=h)).status_code == 204
    assert (await async_client.post(url, json={"action": "view", "position": 1}, headers=h)).status_code == 204
    assert (await async_client.post(url, json={"action": "view"}, headers=h)).status_code == 204  # deduped
    assert (await async_client.post(url, json={"action": "like"}, headers=h)).status_code == 422
    assert (await async_client.post(url, json={"action": "save"})).status_code == 401
    missing = f"{API}/properties/{uuid4()}/interactions"
    assert (await async_client.post(missing, json={"action": "view"}, headers=h)).status_code == 404
    async with AsyncSessionLocal() as s:
        acts = (await s.execute(select(ListingInteraction.action).where(
            ListingInteraction.user_id == market.seeker).order_by(ListingInteraction.created_at))).scalars().all()
    assert acts == ["save", "view"]

    await _get(async_client, market, h, sort="recommended")
    shown = {str(i.property_id): i.features for i in await _impressions(market.seeker)}
    assert shown[str(market.ids["pricey"])]["has_taste"] == 1.0
    assert shown[str(market.ids["pricey"])]["taste_kind"] == 1.0   # the 2BHK they saved
    assert shown[str(market.ids["best"])]["taste_kind"] == 0.0

    async with AsyncSessionLocal() as s:
        s.add(UserPrivacySetting(user_id=market.seeker, personalized_ranking=False))
        await s.execute(delete(ListingInteraction).where(ListingInteraction.user_id == market.seeker))
        await s.commit()
    assert (await async_client.post(url, json={"action": "save"}, headers=h)).status_code == 204
    rows = await _get(async_client, market, h, sort="recommended")
    assert await _impressions(market.seeker) == []
    async with AsyncSessionLocal() as s:
        assert (await s.execute(select(ListingInteraction).where(
            ListingInteraction.user_id == market.seeker))).scalars().all() == []
    # Their stated budget still counts; only their activity is ignored.
    best = next(r for r in rows if r["id"] == str(market.ids["best"]))
    assert "Within your budget" in best["match_reasons"]
    res = await async_client.get(f"{API}/profiles/me/privacy", headers=h)
    assert res.status_code == 200 and res.json()["personalized_ranking"] is False


async def test_price_sort_covers_every_page_and_bad_sorts_are_refused(async_client, market):
    first = await _get(async_client, market, sort="price_asc", limit=2, offset=0)
    second = await _get(async_client, market, sort="price_asc", limit=2, offset=2)
    rents = [float(r["monthly_rent"]) for r in first + second]
    assert rents == sorted(rents) and rents[0] == 13000.0
    top = await _get(async_client, market, sort="price_desc", limit=1)
    assert float(top[0]["monthly_rent"]) == 30000.0
    res = await async_client.get(f"{API}/properties", params={"sort": "random"})
    assert res.status_code == 400


async def test_owner_response_rate(market):
    owner, seeker = market.owners[0], market.seeker
    async with AsyncSessionLocal() as s:
        answered, ignored = Conversation(type="property_inquiry"), Conversation(type="property_inquiry")
        s.add_all([answered, ignored])
        await s.flush()
        for conv in (answered, ignored):
            s.add_all([ConversationParticipant(conversation_id=conv.id, user_id=owner),
                       ConversationParticipant(conversation_id=conv.id, user_id=seeker)])
        asked = datetime.now(timezone.utc) - timedelta(days=2)
        s.add_all([
            Message(conversation_id=answered.id, sender_id=seeker, content="Is it free?", sent_at=asked),
            Message(conversation_id=answered.id, sender_id=owner, content="Yes!", sent_at=asked + timedelta(hours=2)),
            Message(conversation_id=ignored.id, sender_id=seeker, content="Hello?", sent_at=asked),
            Message(conversation_id=ignored.id, sender_id=owner, content="Late", sent_at=asked + timedelta(hours=30)),
        ])
        await s.commit()
        try:
            assert (await owner_response_rates(s, [owner]))[owner] == (2, 1)
        finally:
            await s.execute(delete(Conversation).where(Conversation.id.in_([answered.id, ignored.id])))
            await s.commit()


async def test_training_examples_label_what_people_did_after_being_shown(market):
    seeker = market.seeker
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    feats = dict.fromkeys(LISTING_FEATURES, 0.0)
    async with AsyncSessionLocal() as s:
        s.add_all([
            ListingInteraction(user_id=seeker, property_id=market.ids["best"], action="impression",
                               position=0, features={**feats, "budget_fit": 1.0}, created_at=week_ago),
            ListingInteraction(user_id=seeker, property_id=market.ids["best"], action="view",
                               created_at=week_ago + timedelta(hours=1)),
            ListingInteraction(user_id=seeker, property_id=market.ids["copy"], action="impression",
                               position=1, features=feats, created_at=week_ago),
            # Opened long after the label window: not credited to that impression.
            ListingInteraction(user_id=seeker, property_id=market.ids["copy"], action="view",
                               created_at=week_ago + timedelta(days=5)),
            # Too recent to be settled: left out.
            ListingInteraction(user_id=seeker, property_id=market.ids["pricey"], action="impression",
                               position=2, features=feats),
        ])
        await s.commit()
        examples = [e for e in await build_listing_examples(s) if e.user_id == seeker]
        assert sorted((e.features["budget_fit"], e.label) for e in examples) == [(0.0, 0), (1.0, 1)]
        report = await train_listing_ranker(s, dry_run=True, min_rows=10_000)
        assert "needs at least" in report.reason and not report.activated
        await s.execute(text("SELECT 1"))
