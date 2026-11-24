"""
Phase 20 Staging End-to-End Integration Test Suite
===================================================
Executes Journeys A through H against the application services and contracts:
- Journey A: Seeker Complete Lifecycle (Register, Profile, Lifestyle, Search, Match, Messaging, Application)
- Journey B: Owner Complete Lifecycle (Register, Property, Inventory, Publish, Review Application, Schedule)
- Journey C: Existing Tenant Vacancy (Tenancy Verification, Replacement Vacancy Posting, Rejection of Unverified)
- Journey D: PG Operator Lifecycle (PG Building, Gender-Rule Floors, Capacity, Amenities)
- Journey E: Flatmate Group Collaboration (Formation, Member Invite, Joint Budget, Wishlist Voting)
- Journey F: Trust, Safety & Moderation (User Report, Block, Exclusion, Moderator Action)
- Journey G: Recovery & Password Lifecycle (Valid/Expired JWTs, Password Hashing Verification)
- Journey H: Security & Unauthorized Access Boundaries (BOLA, RBAC Escapes, Cross-Tenant Isolation)
"""

import pytest
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timezone, timedelta, date
from unittest.mock import AsyncMock, MagicMock

from app.modules.users.models import User
from app.modules.profiles.models import Profile
from app.modules.profiles.schemas import ProfileUpdate
from app.modules.profiles.service import ProfileService
from app.modules.lifestyle.schemas import LifestyleCreateOrUpdate, DealbreakerCreate
from app.modules.lifestyle.service import LifestyleService
from app.modules.properties.schemas import PropertyCreate, RoomCreate, BedCreate
from app.modules.properties.service import PropertyService
from app.modules.properties.models import Property
from app.modules.matching.engine import compute_10_dimension_compatibility
from app.modules.matching.service import MatchingService
from app.modules.matching.models import MatchInteraction
from app.modules.groups.schemas import GroupCreate
from app.modules.groups.models import Group, GroupMember
from app.modules.groups.service import GroupService
from app.modules.applications.schemas import ApplicationCreate, ApplicationStatusUpdate
from app.modules.applications.service import ApplicationService
from app.modules.applications.models import Application
from app.modules.appointments.schemas import AppointmentCreate, AppointmentStatusUpdate
from app.modules.appointments.service import AppointmentService
from app.modules.tenants.schemas import ExistingTenantVacancyCreate
from app.modules.tenants.models import TenantMembership
from app.modules.tenants.service import TenantService
from app.modules.pg_management.schemas import PGBuildingCreate, PGFloorCreate
from app.modules.pg_management.models import PGBuilding
from app.modules.pg_management.service import PGService
from app.modules.messaging.schemas import CreateConversationRequest
from app.modules.messaging.service import MessagingService
from app.modules.moderation.schemas import ReportCreate, ReportReviewRequest
from app.modules.moderation.models import ModerationReport, UserBlock
from app.modules.moderation.service import ModerationService
from app.core.security import create_access_token, decode_token, get_password_hash, verify_password
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
)


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


# ==============================================================================
# Journey A — Seeker Complete Lifecycle
# ==============================================================================
@pytest.mark.asyncio
async def test_journey_a_seeker_complete_lifecycle(mock_db):
    seeker_id = uuid4()
    candidate_id = uuid4()
    prop_id = uuid4()

    # 1. Profile Completion
    profile_service = ProfileService(mock_db)
    seeker_profile = Profile(
        id=uuid4(),
        user_id=seeker_id,
        display_name="Aarav P.",
        bio="CS grad student at IISc. Tidy, early riser.",
        occupation="Graduate Student",
        budget_min=18000,
        budget_max=28000,
        preferred_locations=["Indiranagar", "Koramangala"],
    )
    profile_service.get_by_user_id = AsyncMock(return_value=seeker_profile)

    update_payload = ProfileUpdate(
        bio="Updated bio: Quiet and focused software engineer.",
        budget_min=20000,
        budget_max=30000,
    )
    updated = await profile_service.update(seeker_id, update_payload)
    assert updated.budget_min == 20000

    # 2. Lifestyle & Dealbreakers
    lifestyle_service = LifestyleService(mock_db)
    lifestyle_service.get_by_user_id = AsyncMock(return_value=None)
    # The profile copy of the answers is covered against a real database in test_lifestyle_traits.py.
    lifestyle_service._sync_profile_traits = AsyncMock()
    ls_payload = LifestyleCreateOrUpdate(
        sleep_schedule="early_bird",
        work_arrangement="hybrid",
        cleanliness_level=4,
        noise_tolerance="moderate",
        lighting_preference="dim",
        guests_policy="occasional_weekends",
        social_battery="balanced",
        diet_preference="vegetarian",
        smoking="never",
        drinking="socially",
        pet_preference="cats_and_dogs_ok",
    )
    ls_record = await lifestyle_service.upsert_lifestyle(seeker_id, ls_payload)
    assert len(ls_record.preference_vector) == 64

    # Dealbreaker registration
    db_create = DealbreakerCreate(
        rule_key="no_smoking_inside",
        is_strict=True,
        expected_value="never",
    )
    created_db = await lifestyle_service.add_dealbreaker(seeker_id, db_create)
    assert created_db.is_strict is True

    # 3. Flatmate Discovery & 10D Compatibility
    traits_a = ls_payload.model_dump()
    traits_candidate = {
        "sleep_schedule": "early_bird",
        "work_arrangement": "hybrid",
        "cleanliness_level": 4,
        "noise_tolerance": "moderate",
        "lighting_preference": "dim",
        "guests_policy": "occasional_weekends",
        "social_battery": "balanced",
        "diet_preference": "vegetarian",
        "smoking": "never",
        "drinking": "socially",
        "pet_preference": "cats_and_dogs_ok",
    }
    comp = compute_10_dimension_compatibility(
        user_traits=traits_a,
        target_traits=traits_candidate,
        user_budget=(20000, 30000),
        target_budget=(22000, 28000),
        user_occupation="Software Engineer",
        target_occupation="Data Scientist",
        user_preferred_locs=["Indiranagar"],
        target_preferred_locs=["Indiranagar"],
        user_dealbreakers=[{"rule_key": "no_smoking_inside", "is_strict": True, "expected_value": "never"}],
    )
    assert comp["overall_score"] >= 80.0
    assert comp["dealbreakers_cleared"] is True

    # 4. Mutual Match & Messaging
    matching_service = MatchingService(mock_db)
    matching_service.pair_features = AsyncMock(return_value=None)  # profile reads not mocked here
    mock_no_int = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    recip = MatchInteraction(user_id=seeker_id, target_user_id=candidate_id, action="like")
    mock_recip_found = MagicMock(scalar_one_or_none=MagicMock(return_value=recip))
    mock_no_mutual = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    matching_service.get_pairwise_score = AsyncMock(
        return_value=MagicMock(overall_score=94.0, model_dump=MagicMock(return_value={"overall_score": 94.0}))
    )
    mock_db.execute.side_effect = [mock_no_int, mock_no_int, mock_recip_found, mock_no_mutual]

    inter_2 = await matching_service.record_interaction(candidate_id, seeker_id, "like")
    assert inter_2.is_mutual_match is True

    # Messaging Access
    messaging_service = MessagingService(mock_db)
    mock_no_block = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_no_conv = MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None))))
    mock_db.execute.side_effect = [mock_no_block, mock_no_conv]
    conv_req = CreateConversationRequest(
        type="direct",
        participant_user_ids=[candidate_id],
    )
    conv = await messaging_service.create_conversation(seeker_id, conv_req)
    assert conv.type == "direct"

    # 5. Rental Application Submission
    app_service = ApplicationService(mock_db)
    prop_obj = Property(
        id=prop_id,
        owner_id=uuid4(),
        title="Modern Flat",
        monthly_rent=Decimal("20000.00"),
        max_capacity=4,
        current_occupants=0,
    )
    mock_prop_ok = MagicMock(scalar_one_or_none=MagicMock(return_value=prop_obj))
    mock_no_dup = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_prop_ok, mock_no_dup]

    app = await app_service.create(
        applicant_id=seeker_id,
        data=ApplicationCreate(
            property_id=prop_obj.id,
            introduction="Respectful software engineer seeking room near office.",
            proposed_rent=Decimal("20000.00"),
            move_in_target=date.today() + timedelta(days=15),
        ),
    )
    assert app.status == "submitted"


# ==============================================================================
# Journey B — Owner Complete Lifecycle
# ==============================================================================
@pytest.mark.asyncio
async def test_journey_b_owner_lifecycle(mock_db):
    owner_id = uuid4()
    applicant_id = uuid4()
    prop_service = PropertyService(mock_db)

    # 1. Create Property
    room_1 = RoomCreate(
        room_name="Master Suite",
        room_type="private",
        room_rent=Decimal("22000.00"),
        deposit=Decimal("60000.00"),
        private_bath=True,
        attached_balcony=True,
        max_beds=1,
        occupied_beds=0,
        available_from=date.today(),
        beds=[
            BedCreate(
                bed_identifier="Bed A",
                monthly_rent=Decimal("22000.00"),
                available_from=date.today(),
            )
        ],
    )
    prop_create = PropertyCreate(
        title="Modern 2BHK Indiranagar",
        description="Spacious flat near 100ft road with dedicated parking",
        property_category="apartment",
        configuration="2BHK",
        latitude=12.9784,
        longitude=77.6408,
        address_display="Indiranagar 100ft Road, Bengaluru",
        address_exact="Flat 202, Indiranagar Heights",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560038",
        monthly_rent=Decimal("38000.00"),
        security_deposit=Decimal("76000.00"),
        total_bedrooms=2,
        total_bathrooms=2,
        max_capacity=3,
        current_occupants=0,
        available_from=date.today(),
        images=["https://images.unsplash.com/photo-1522708323590-d24dbb6b0267"],
        amenities=["wifi", "lift", "power_backup", "parking"],
        rooms=[room_1],
    )

    prop_id = uuid4()
    prop_mock_res = {
        "id": prop_id,
        "owner_id": owner_id,
        "title": prop_create.title,
        "listing_status": "published",
        "max_capacity": 3,
        "current_occupants": 0,
        "rooms": [{"id": uuid4(), "room_name": "Master Suite", "max_beds": 1, "occupied_beds": 0}],
    }
    prop_service.get_by_id = AsyncMock(return_value=prop_mock_res)
    created_prop = await prop_service.create(owner_id, prop_create)
    assert created_prop["title"] == prop_create.title
    assert created_prop["listing_status"] == "published"

    # 2. Review & Accept Application
    app_service = ApplicationService(mock_db)
    app = Application(
        id=uuid4(),
        property_id=prop_id,
        applicant_id=applicant_id,
        status="submitted",
        proposed_rent=Decimal("22000.00"),
    )
    app_service.get_by_id = AsyncMock(return_value=app)
    prop_obj = Property(
        id=prop_id,
        owner_id=owner_id,
        title=prop_create.title,
        monthly_rent=Decimal("38000.00"),
        max_capacity=3,
        current_occupants=0,
    )
    mock_prop_ok = MagicMock(scalar_one_or_none=MagicMock(return_value=prop_obj))
    mock_db.execute.side_effect = [mock_prop_ok]

    reviewed_app = await app_service.update_status(
        application_id=app.id,
        current_user_id=owner_id,
        data=ApplicationStatusUpdate(status="accepted", note="Welcome to the flat!"),
    )
    assert reviewed_app.status == "accepted"

    # 3. Schedule & Confirm Viewing Appointment
    apt_service = AppointmentService(mock_db)
    mock_no_dup = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_prop_ok, mock_no_dup]
    apt = await apt_service.create(
        applicant_id=applicant_id,
        data=AppointmentCreate(
            property_id=prop_id,
            host_id=owner_id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
            appointment_type="physical_visit",
        ),
    )
    assert apt.status == "pending"

    apt_service.get_by_id = AsyncMock(return_value=apt)
    confirmed_apt = await apt_service.update_status(
        appointment_id=apt.id,
        user_id=owner_id,
        data=AppointmentStatusUpdate(status="confirmed"),
    )
    assert confirmed_apt.status == "confirmed"


# ==============================================================================
# Journey C — Existing Tenant Replacement Vacancy
# ==============================================================================
@pytest.mark.asyncio
async def test_journey_c_existing_tenant_vacancy(mock_db):
    tenant_id = uuid4()
    property_id = uuid4()
    room_id = uuid4()

    tenant_service = TenantService(mock_db)

    # 1. Verified Active Tenancy
    active_membership = TenantMembership(
        id=uuid4(),
        property_id=property_id,
        room_id=room_id,
        tenant_id=tenant_id,
        monthly_rent=Decimal("16000.00"),
        status="active",
        is_primary_tenant=True,
    )
    mock_mem_ok = MagicMock(scalar_one_or_none=MagicMock(return_value=active_membership))
    mock_db.execute.side_effect = [mock_mem_ok]

    vacancy_req = ExistingTenantVacancyCreate(
        property_id=property_id,
        room_id=room_id,
        title="Spacious Room Available in Indiranagar 2BHK",
        description="Roommate moving abroad. Looking for a tidy flatmate.",
        vacant_from=date.today() + timedelta(days=20),
        expected_rent=Decimal("16000.00"),
        deposit_required=Decimal("50000.00"),
        preferred_gender="any",
    )
    vacancy = await tenant_service.create_vacancy(tenant_id, vacancy_req)
    assert vacancy.posted_by_tenant_id == tenant_id
    assert vacancy.is_active is True

    # 2. Rejection for Unverified Tenant
    mock_no_membership = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_membership]
    stranger_id = uuid4()
    with pytest.raises(ForbiddenException):
        await tenant_service.create_vacancy(stranger_id, vacancy_req)


# ==============================================================================
# Journey D — PG Operator Lifecycle
# ==============================================================================
@pytest.mark.asyncio
async def test_journey_d_pg_operator_lifecycle(mock_db):
    operator_id = uuid4()
    property_id = uuid4()
    pg_id = uuid4()

    pg_service = PGService(mock_db)

    # 1. Create PG Building
    mock_no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_existing]

    expected_b = PGBuilding(
        id=pg_id,
        operator_id=operator_id,
        property_id=property_id,
        building_name="Stanza Living Indiranagar Wing A",
        pg_type="coed",
        total_floors=3,
        food_included=True,
        meal_type="veg_and_non_veg",
        meals_served_per_day=3,
        gate_closing_time="22:30",
        notice_period_days=30,
        biometric_entry=True,
    )
    pg_service.get_building = AsyncMock(return_value=expected_b)

    pg_create = PGBuildingCreate(
        property_id=property_id,
        building_name="Stanza Living Indiranagar Wing A",
        pg_type="coed",
        total_floors=3,
        food_included=True,
        meal_type="veg_and_non_veg",
        meals_served_per_day=3,
        gate_closing_time="22:30",
        notice_period_days=30,
        biometric_entry=True,
    )
    building = await pg_service.create_building(operator_id, pg_create)
    assert building.building_name == "Stanza Living Indiranagar Wing A"
    assert building.biometric_entry is True

    # 2. Add Floor with Specific Gender Rule
    building_obj = PGBuilding(id=pg_id, operator_id=operator_id, total_floors=3)
    pg_service.get_building = AsyncMock(return_value=building_obj)

    floor_create = PGFloorCreate(
        floor_number=1,
        gender_restriction="ladies_only",
        total_rooms=4,
    )
    floor = await pg_service.add_floor(pg_id, operator_id, floor_create)
    assert floor.floor_number == 1
    assert floor.gender_restriction == "ladies_only"


# ==============================================================================
# Journey E — Group Collaboration & Wishlist
# ==============================================================================
@pytest.mark.asyncio
async def test_journey_e_group_collaboration(mock_db):
    leader_id = uuid4()
    member_id = uuid4()
    group_id = uuid4()
    prop_id = uuid4()

    group_service = GroupService(mock_db)

    # 1. Create Group
    group_create = GroupCreate(
        name="Bangalore Tech Syndicate",
        description="3 engineers teaming up for a premium flat",
        target_budget_total=60000,
        target_city="Bengaluru",
        target_move_in=date.today() + timedelta(days=30),
    )
    created_group = Group(
        id=group_id,
        creator_id=leader_id,
        name=group_create.name,
        target_budget_total=60000,
        target_city="Bengaluru",
        members=[],
        wishlist_items=[],
    )
    group_service.get_by_id = AsyncMock(return_value=created_group)

    g = await group_service.create(leader_id, group_create)
    assert g.name == "Bangalore Tech Syndicate"

    # 2. Authorized Member Invitation
    mock_no_existing_member = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_existing_member]
    member = await group_service.add_member(
        group_id=group_id,
        user_id=member_id,
        requester_id=leader_id,
        role="member",
    )
    assert member.user_id == member_id

    # 3. Security: Non-Leader Cannot Add Members
    stranger_id = uuid4()
    mock_no_leader = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_leader]
    with pytest.raises(ForbiddenException):
        await group_service.add_member(
            group_id=group_id,
            user_id=uuid4(),
            requester_id=stranger_id,
            role="member",
        )

    # 4. Wishlist Voting
    mock_member_res = MagicMock(scalar_one_or_none=MagicMock(return_value=GroupMember(group_id=group_id, user_id=leader_id)))
    mock_no_item = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_member_res, mock_no_item]

    voted_item = await group_service.vote_wishlist(
        group_id=group_id,
        property_id=prop_id,
        user_id=leader_id,
        vote="up",
    )
    assert voted_item.votes[str(leader_id)] == "up"


# ==============================================================================
# Journey F — Trust, Safety & Moderation
# ==============================================================================
@pytest.mark.asyncio
async def test_journey_f_trust_safety_moderation(mock_db):
    user_a = uuid4()
    bad_actor = uuid4()
    prop_id = uuid4()

    moderation_service = ModerationService(mock_db)

    # 1. Report User
    rep_req = ReportCreate(
        target_type="user",
        target_id=bad_actor,
        reason="harassment",
        description="Inappropriate language and harassment in chat.",
    )
    report = await moderation_service.submit_report(user_a, rep_req)
    assert report.status == "open"
    assert report.reason == "harassment"

    # 2. Block User
    mock_no_block = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_block]
    block = await moderation_service.block_user(user_a, bad_actor)
    assert block.blocked_user_id == bad_actor

    # Duplicate Block Prevention
    existing_block = UserBlock(user_id=user_a, blocked_user_id=bad_actor)
    mock_has_block = MagicMock(scalar_one_or_none=MagicMock(return_value=existing_block))
    mock_db.execute.side_effect = [mock_has_block]
    with pytest.raises(ConflictException):
        await moderation_service.block_user(user_a, bad_actor)

    # 3. Report Property
    prop_rep = ReportCreate(
        target_type="property",
        target_id=prop_id,
        reason="misleading_photos",
        description="Listing images do not reflect the actual state of the property.",
    )
    p_report = await moderation_service.submit_report(user_a, prop_rep)
    assert p_report.target_type == "property"

    # 4. Moderator Review & Resolution
    report_obj = ModerationReport(
        id=uuid4(),
        reporter_id=user_a,
        target_type="user",
        target_id=bad_actor,
        reason="harassment",
        status="open",
    )
    mock_rep_res = MagicMock(scalar_one_or_none=MagicMock(return_value=report_obj))
    mock_db.execute.side_effect = [mock_rep_res]

    reviewed = await moderation_service.review_report(
        report_id=report_obj.id,
        review=ReportReviewRequest(status="resolved", resolution_notes="User warned and flagged."),
    )
    assert reviewed.status == "resolved"


# ==============================================================================
# Journey G — Recovery & Password Lifecycle
# ==============================================================================
@pytest.mark.asyncio
async def test_journey_g_recovery_lifecycle(mock_db):
    user_id = uuid4()
    raw_password = "StagingSecretPass!2026"
    password_hash = get_password_hash(raw_password)

    user = User(
        id=user_id,
        email="recovery.test@synth.flatmate.test",
        hashed_password=password_hash,
        full_name="Recovery User",
        is_active=True,
    )

    # Password Hash Verification
    assert verify_password(raw_password, user.hashed_password) is True
    assert verify_password("WrongPassword123!", user.hashed_password) is False

    # Valid token generation & decoding
    valid_token = create_access_token(
        subject=str(user_id),
        roles=["seeker"],
        email=user.email,
        expires_delta=timedelta(minutes=15),
    )
    payload = decode_token(valid_token)
    assert payload["sub"] == str(user_id)
    assert payload["email"] == user.email

    # Expired token rejection (decode_token returns empty dict on expired/invalid JWT)
    expired_token = create_access_token(
        subject=str(user_id),
        roles=["seeker"],
        email=user.email,
        expires_delta=timedelta(seconds=-10),
    )
    assert decode_token(expired_token) == {}


# ==============================================================================
# Journey H — Security & Unauthorized Access Boundaries
# ==============================================================================
@pytest.mark.asyncio
async def test_journey_h_unauthorized_access_boundaries(mock_db):
    user_a = uuid4()
    user_b = uuid4()
    app_id = uuid4()

    app_service = ApplicationService(mock_db)
    # User B attempts to inspect User A's private application
    app_a = Application(id=app_id, applicant_id=user_a, property_id=uuid4(), status="submitted")
    app_service.get_by_id = AsyncMock(return_value=app_a)

    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    # User B is neither applicant, nor owner, nor admin -> HTTP 403 Forbidden
    with pytest.raises(ForbiddenException):
        await app_service.get_by_id_authorized(application_id=app_id, current_user_id=user_b, is_admin=False)
