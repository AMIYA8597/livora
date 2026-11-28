"""
End-to-End User Journey Integration Tests.
Executes the complete marketplace lifecycle across multi-role actors:
1. Registration & Profile / 10-Dimension Lifestyle Setup
2. Property & Room Inventory Creation (Owner)
3. Geospatial / Structured Listing Discovery (Tenant)
4. Pairwise Explainable Compatibility & Reciprocal Matching
5. Group Formation, Collective Scoring & Shared Wishlist Voting
6. Rental Application Lifecycle & Status State Machine
7. Viewing Appointment Scheduling with Overlap Conflict Prevention
8. Secure Messaging with In-Flight Safety / Scam Moderation
9. Administrative Platform Audit
"""

from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.main import app
from app.modules.users.models import User
from app.modules.profiles.models import Profile
from app.modules.properties.schemas import PropertyCreate
from app.modules.properties.service import PropertyService
from app.modules.matching.engine import compute_10_dimension_compatibility
from app.modules.matching.service import MatchingService
from app.modules.matching.models import MatchInteraction
from tests.matching_mocks import interactions_found
from app.modules.groups.service import GroupService
from app.modules.groups.schemas import GroupCreate
from app.modules.groups.models import Group, GroupMember
from app.modules.applications.service import ApplicationService
from app.modules.applications.schemas import ApplicationCreate, ApplicationStatusUpdate
from app.modules.appointments.service import AppointmentService
from app.modules.appointments.schemas import AppointmentCreate, AppointmentStatusUpdate
from app.ml.embeddings import LocalHashingEmbedder, cosine
from app.ml.moderation import prescreen
from app.modules.moderation.service import ModerationService
from app.modules.moderation.schemas import ReportCreate
from app.modules.administration.service import AdminService


@pytest.mark.asyncio
@pytest.mark.usefixtures("stub_city_catalogue")
async def test_full_marketplace_end_to_end_journey():
    """
    Simulates complete cross-functional workflow from registration to administrative oversight.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    # =========================================================================
    # Step 1: Actors Creation & Profiles
    # =========================================================================
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    owner_c_id = uuid4()
    admin_d_id = uuid4()
    assert admin_d_id is not None

    tenant_a_user = User(
        id=tenant_a_id,
        email="rahul.tech@example.com",
        full_name="Rahul Sharma",
        phone_number="+919876543210",
        role="working_professional",
        is_verified=False,
    )
    assert tenant_a_user.id == tenant_a_id
    tenant_b_user = User(
        id=tenant_b_id,
        email="priya.fin@example.com",
        full_name="Priya Patel",
        phone_number="+919876543211",
        role="working_professional",
        is_verified=True,
    )
    assert tenant_b_user.id == tenant_b_id

    owner_c_user = User(
        id=owner_c_id,
        email="rajesh.owner@example.com",
        full_name="Rajesh Rao",
        phone_number="+919876543212",
        role="property_owner",
        is_verified=True,
    )
    assert owner_c_user.id == owner_c_id

    tenant_a_profile = Profile(
        user_id=tenant_a_id,
        display_name="Rahul S",
        bio="Senior Backend Engineer at a tech firm. Early riser and tidy.",
        company_name="Acme Tech",
        designation="Lead Architect",
        budget_min=15000,
        budget_max=25000,
    )
    assert tenant_a_profile.user_id == tenant_a_id

    # 10-Dimension Lifestyle Traits
    traits_a = {
        "work_arrangement": "hybrid",
        "sleep_schedule": "early_bird",
        "cleanliness_level": 4,
        "smoking": "never",
        "drinking": "socially",
        "diet_preference": "vegetarian",
        "noise_tolerance": "moderate",
        "lighting_preference": "dim",
        "guests_policy": "occasional_weekends",
        "social_battery": "balanced",
    }
    traits_b = {
        "work_arrangement": "hybrid",
        "sleep_schedule": "early_bird",
        "cleanliness_level": 4,
        "smoking": "never",
        "drinking": "socially",
        "diet_preference": "vegetarian",
        "noise_tolerance": "moderate",
        "lighting_preference": "dim",
        "guests_policy": "occasional_weekends",
        "social_battery": "balanced",
    }

    # =========================================================================
    # Step 2: Property Creation by Owner
    # =========================================================================
    prop_service = PropertyService(mock_db)
    prop_payload = PropertyCreate(
        title="Sunlit 2BHK Apartment in Koramangala 4th Block",
        description="Premium gated society with gym, 24/7 power backup, and high-speed fiber.",
        property_category="apartment",
        configuration="2BHK",
        latitude=12.9352,
        longitude=77.6245,
        address_display="Koramangala 4th Block, Bengaluru",
        address_exact="Flat 302, Green Glen Apartments, 4th Cross",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560034",
        monthly_rent=Decimal("38000.00"),
        security_deposit=Decimal("100000.00"),
        max_capacity=2,
        available_from=date.today(),
        currency="INR",
    )

    prop_id = uuid4()
    prop_mock = MagicMock(
        id=prop_id,
        title=prop_payload.title,
        monthly_rent=Decimal("38000.00"),
        listing_status="draft",
        description=prop_payload.description,
        locality="Koramangala",
        owner_id=owner_c_id,
    )
    prop_service.get_by_id = AsyncMock(return_value=prop_mock)

    created_prop = await prop_service.create(owner_id=owner_c_id, data=prop_payload)
    assert created_prop.title == prop_payload.title
    assert created_prop.monthly_rent == Decimal("38000.00")
    assert created_prop.listing_status == "draft"

    # =========================================================================
    # Step 3: Discovery Search (Keyword & Locality)
    # =========================================================================
    # Embedding similarity (local provider): the Koramangala 2BHK ranks above the Whitefield 1BHK.
    embedder = LocalHashingEmbedder()
    query_vec, ours, other = await embedder.embed(
        ["Koramangala 2BHK", f"{created_prop.title} {created_prop.description} Koramangala",
         "1BHK in Whitefield near ITPL. Quiet flat near tech parks. Whitefield"],
        kind="document",
    )
    assert cosine(query_vec, ours) > cosine(query_vec, other)

    # =========================================================================
    # Step 4: Pairwise 10-Dimension Compatibility & Mutual Matching
    # =========================================================================
    comp = compute_10_dimension_compatibility(
        user_traits=traits_a,
        target_traits=traits_b,
        user_budget=(15000, 25000),
        target_budget=(15000, 22000),
        user_occupation="Software Engineer",
        target_occupation="Data Analyst",
        user_domain="Technology",
        target_domain="Technology",
        user_preferred_locs=["Koramangala", "HSR Layout"],
        target_preferred_locs=["Koramangala"],
    )
    assert comp["overall_score"] >= 85.0
    assert comp["dealbreakers_cleared"] is True
    assert "working_schedule" in comp["factors"]
    assert "cleanliness" in comp["factors"]

    # Mutual Reciprocal Matching Interaction
    matching_service = MatchingService(mock_db)
    # Ranking-feature snapshots read profiles; covered by tests/test_ml_platform_db.py.
    matching_service._pair_scores = AsyncMock(return_value=None)

    # Actor A likes Actor B
    mock_no_block = MagicMock()
    mock_no_block.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_no_block, interactions_found()]  # neither has decided yet

    res_a = await matching_service.record_interaction(
        user_id=tenant_a_id,
        target_user_id=tenant_b_id,
        action="like",
    )
    assert res_a.action == "like"
    assert res_a.is_mutual_match is False

    # Actor B likes Actor A -> Mutual Match!
    reciprocal_match_from_a = MatchInteraction(user_id=tenant_a_id, target_user_id=tenant_b_id, action="like")
    mock_existing_mutual = MagicMock()
    mock_existing_mutual.scalar_one_or_none.return_value = None

    pairwise_mock = MagicMock(overall_score=92.5, model_dump=MagicMock(return_value={"overall_score": 92.5}))
    matching_service.get_pairwise_score = AsyncMock(return_value=pairwise_mock)

    mock_db.execute.side_effect = [mock_no_block, interactions_found(reciprocal_match_from_a), mock_existing_mutual]
    res_b = await matching_service.record_interaction(
        user_id=tenant_b_id,
        target_user_id=tenant_a_id,
        action="like",
    )
    assert res_b.is_mutual_match is True

    # =========================================================================
    # Step 5: Group Formation & Shared Wishlist
    # =========================================================================
    group_service = GroupService(mock_db)
    group_id = uuid4()
    group_obj = Group(
        id=group_id,
        creator_id=tenant_a_id,
        name="Koramangala Tech & Finance Explorers",
        target_budget_total=45000,
        target_city="Bengaluru",
        members=[],
        wishlist_items=[],
    )
    group_service.get_by_id = AsyncMock(return_value=group_obj)

    group_res = await group_service.create(
        creator_id=tenant_a_id,
        data=GroupCreate(
            name="Koramangala Tech & Finance Explorers",
            target_budget_total=45000,
            target_city="Bengaluru",
        ),
    )
    assert group_res.name == "Koramangala Tech & Finance Explorers"
    assert group_res.creator_id == tenant_a_id

    # Add Actor B to the Group
    mock_no_member = MagicMock()
    mock_no_member.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_no_member]
    added_member = await group_service.add_member(
        group_id=group_id,
        user_id=tenant_b_id,
        role="member",
    )
    assert added_member.user_id == tenant_b_id

    # Member votes up the target property in the shared wishlist
    mock_member_ok = MagicMock()
    mock_member_ok.scalar_one_or_none.return_value = GroupMember(group_id=group_id, user_id=tenant_a_id)
    mock_no_vote = MagicMock()
    mock_no_vote.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_member_ok, mock_no_vote]
    vote_res = await group_service.vote_wishlist(
        group_id=group_id,
        property_id=created_prop.id,
        user_id=tenant_a_id,
        vote="up",
    )
    assert vote_res.property_id == created_prop.id
    assert vote_res.votes[str(tenant_a_id)] == "up"

    # =========================================================================
    # Step 6: Rental Application Lifecycle
    # =========================================================================
    app_service = ApplicationService(mock_db)

    # Actor A applies for the property
    mock_prop_for_app = MagicMock()
    mock_prop_for_app.scalar_one_or_none.return_value = created_prop
    mock_no_dup_app = MagicMock()
    mock_no_dup_app.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_prop_for_app, mock_no_dup_app]

    application = await app_service.create(
        applicant_id=tenant_a_id,
        data=ApplicationCreate(
            property_id=created_prop.id,
            introduction="We are two working professionals looking to lease your 2BHK flat.",
            proposed_rent=Decimal("38000.00"),
            move_in_target=date.today() + timedelta(days=15),
        ),
    )
    assert application.status == "submitted"

    # Owner reviews application
    app_service.get_by_id = AsyncMock(return_value=application)
    mock_prop_owner = MagicMock()
    mock_prop_owner.scalar_one_or_none.return_value = created_prop
    mock_db.execute.side_effect = [mock_prop_owner]

    updated_app = await app_service.update_status(
        application_id=application.id,
        current_user_id=owner_c_id,
        data=ApplicationStatusUpdate(status="accepted", note="All documents verified."),
    )
    assert updated_app.status == "accepted"

    # =========================================================================
    # Step 7: Viewing Appointment & Conflict Prevention
    # =========================================================================
    apt_service = AppointmentService(mock_db)
    scheduled_time = datetime.now(timezone.utc) + timedelta(days=2, hours=4)

    mock_prop_apt = MagicMock()
    mock_prop_apt.scalar_one_or_none.return_value = created_prop
    mock_no_apt_conflict = MagicMock()
    mock_no_apt_conflict.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_prop_apt, mock_no_apt_conflict]

    apt = await apt_service.create(
        applicant_id=tenant_a_id,
        data=AppointmentCreate(
            property_id=created_prop.id,
            host_id=owner_c_id,
            scheduled_at=scheduled_time,
            appointment_type="physical_visit",
            notes="Please share gate pass entry details.",
        ),
    )
    assert apt.status == "pending"

    # Host confirms appointment
    apt_service.get_by_id = AsyncMock(return_value=apt)
    confirmed_apt = await apt_service.update_status(
        appointment_id=apt.id,
        user_id=owner_c_id,
        data=AppointmentStatusUpdate(status="confirmed"),
    )
    assert confirmed_apt.status == "confirmed"

    # =========================================================================
    # Step 8: Messaging & Safety Heuristic Moderation
    # =========================================================================
    clean_msg = "Hello Rajesh, we are looking forward to our flat viewing this Saturday."
    assert prescreen(clean_msg).level == "clear"

    # Scam message: recipients see a warning at once; AI moderation reviews it in the worker.
    scam_msg = "Please transfer money advance before visit via Paytm to confirm key handover."
    screen = prescreen(scam_msg)
    assert screen.level == "high" and screen.warning

    # =========================================================================
    # Step 9: Safety Moderation Reporting & Admin Audit
    # =========================================================================
    moderation_service = ModerationService(mock_db)
    bad_actor_id = uuid4()

    mock_no_report = MagicMock()
    mock_no_report.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_no_report]
    report = await moderation_service.submit_report(
        reporter_id=tenant_a_id,
        data=ReportCreate(
            target_type="user",
            target_id=bad_actor_id,
            reason="scam",
            description="Demanded ₹10,000 token before permitting property entry.",
        ),
    )
    assert report.status == "open"

    # Audit platform statistics via AdminService
    admin_service = AdminService(mock_db)
    mock_db.execute.side_effect = None
    mock_scalar = MagicMock(side_effect=[142, 68, 55, 34, 12, 3])
    mock_exec_res = MagicMock()
    mock_exec_res.scalar = mock_scalar
    mock_db.execute.return_value = mock_exec_res
    stats = await admin_service.get_platform_stats()
    assert stats.total_users == 142
    assert stats.total_properties == 68
    assert stats.total_active_listings == 55
    assert stats.total_mutual_matches == 34


def test_openapi_schema_generation():
    """Verify OpenAPI 3.x schema generates cleanly without missing schemas or syntax errors."""
    openapi_schema = app.openapi()
    assert openapi_schema is not None
    assert openapi_schema["openapi"].startswith("3.")
    assert openapi_schema["info"]["title"] == "Flatmate Platform"
    assert "/api/v1/search/properties" in openapi_schema["paths"]
    assert "/api/v1/matching/recommendations" in openapi_schema["paths"]
    assert "/api/v1/groups/" in openapi_schema["paths"]
    assert "/api/v1/applications/" in openapi_schema["paths"]
    assert "/api/v1/appointments/" in openapi_schema["paths"]
    assert "/health" in openapi_schema["paths"]
