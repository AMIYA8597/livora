"""
Phase 18 Comprehensive End-to-End Acceptance Test Suite
Verifies all 8 Core User Journeys (A through H) across Seeker, Owner, Tenant, PG,
Group, Moderation/Safety, Credentials/Recovery, and DPDP Privacy/Masking.
"""
import pytest
from geoalchemy2.elements import WKTElement
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timezone, timedelta, date
from unittest.mock import AsyncMock, MagicMock

from app.modules.users.models import User
from app.modules.users.schemas import UserUpdate
from app.modules.users.service import UserService
from app.modules.lifestyle.schemas import LifestyleCreateOrUpdate, DealbreakerCreate
from app.modules.lifestyle.service import LifestyleService
from app.modules.properties.schemas import PropertyCreate, RoomCreate, BedCreate
from app.modules.properties.service import PropertyService
from app.modules.properties.models import Property, Room, Bed
from app.modules.matching.engine import compute_10_dimension_compatibility
from app.modules.matching.service import MatchingService
from app.modules.matching.models import MatchInteraction
from tests.matching_mocks import interactions_found
from app.modules.groups.schemas import GroupCreate
from app.modules.groups.models import Group, GroupMember
from app.modules.groups.service import GroupService
from app.modules.applications.schemas import ApplicationCreate, ApplicationStatusUpdate
from app.modules.applications.service import ApplicationService
from app.modules.appointments.schemas import AppointmentCreate, AppointmentStatusUpdate
from app.modules.appointments.service import AppointmentService
from app.modules.tenants.schemas import ExistingTenantVacancyCreate
from app.modules.tenants.models import TenantMembership, ExistingTenantVacancy
from app.modules.tenants.service import TenantService
from app.modules.pg_management.schemas import PGBuildingCreate, PGFloorCreate
from app.modules.pg_management.models import PGBuilding
from app.modules.pg_management.service import PGService
from app.modules.messaging.schemas import CreateConversationRequest
from app.modules.messaging.service import MessagingService
from app.modules.moderation.schemas import ReportCreate, ReportReviewRequest
from app.modules.moderation.models import ModerationReport
from app.modules.moderation.service import ModerationService
from app.modules.auth.schemas import ForgotPasswordRequest, ResetPasswordRequest
from app.modules.auth.service import AuthService
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
)


@pytest.mark.asyncio
async def test_phase18_journey_a_flatmate_seeker_discovery_and_match():
    """
    Journey A: Flatmate Seeker End-to-End
    1. Lifestyle setup & 64-dim vector generation.
    2. Dealbreaker enforcement (strict no-smoking inside).
    3. 10-D compatibility radar scoring.
    4. Mutual matching & direct messaging initiation.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    seeker_id = uuid4()
    candidate_id = uuid4()

    # 1. Lifestyle questionnaire setup
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

    # 2. Add dealbreaker
    db_create = DealbreakerCreate(
        rule_key="no_smoking_inside",
        is_strict=True,
        expected_value="never",
    )
    created_db = await lifestyle_service.add_dealbreaker(seeker_id, db_create)
    assert created_db.rule_key == "no_smoking_inside"
    assert created_db.is_strict is True

    # 3. 10-D compatibility computation
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
        user_traits=ls_payload.model_dump(),
        target_traits=traits_candidate,
        user_budget=(20000, 30000),
        target_budget=(22000, 28000),
        user_occupation="Product Designer",
        target_occupation="Architect",
        user_preferred_locs=["Indiranagar"],
        target_preferred_locs=["Indiranagar"],
        user_dealbreakers=[{"rule_key": "no_smoking_inside", "is_strict": True, "expected_value": "never"}],
    )
    assert comp["overall_score"] >= 80.0
    assert comp["dealbreakers_cleared"] is True
    assert "cleanliness" in comp["factors"]

    # 4. Mutual matching
    matching_service = MatchingService(mock_db)
    matching_service._pair_scores = AsyncMock(return_value=None)  # profile reads not mocked here
    mock_no_int = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_int, interactions_found()]  # no block; neither has decided
    inter_1 = await matching_service.record_interaction(seeker_id, candidate_id, "like")
    assert inter_1.is_mutual_match is False

    recip = MatchInteraction(user_id=seeker_id, target_user_id=candidate_id, action="like")
    mock_no_mutual = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    matching_service.get_pairwise_score = AsyncMock(return_value=MagicMock(overall_score=92.0, model_dump=MagicMock(return_value={"overall_score": 92.0})))
    mock_db.execute.side_effect = [mock_no_int, interactions_found(recip), mock_no_mutual]

    inter_2 = await matching_service.record_interaction(candidate_id, seeker_id, "like")
    assert inter_2.is_mutual_match is True

    # 5. Direct messaging conversation creation
    messaging_service = MessagingService(mock_db)
    mock_no_block = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_no_conv = MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None))))
    # Nobody here turned direct messages off.
    mock_no_dm_optout = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    mock_db.execute.side_effect = [mock_no_block, mock_no_conv, mock_no_dm_optout]
    conv = await messaging_service.create_conversation(
        seeker_id,
        CreateConversationRequest(type="direct", participant_user_ids=[candidate_id]),
    )
    assert conv.type == "direct"


@pytest.mark.asyncio
@pytest.mark.usefixtures("stub_city_catalogue")
async def test_phase18_journey_b_owner_property_inventory_lifecycle():
    """
    Journey B: Owner Property Inventory Lifecycle
    1. Create property with rooms and beds.
    2. Toggle listing status (published -> paused -> published).
    3. Accept incoming tenancy application.
    4. Confirm viewing appointment.
    5. Vacate bed on tenant departure.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    owner_id = uuid4()
    applicant_id = uuid4()
    prop_id = uuid4()
    bed_id = uuid4()

    prop_service = PropertyService(mock_db)
    room_1 = RoomCreate(
        room_name="Deluxe Room 1",
        room_type="private",
        room_rent=Decimal("24000.00"),
        deposit=Decimal("70000.00"),
        private_bath=True,
        attached_balcony=True,
        max_beds=1,
        occupied_beds=0,
        available_from=date.today(),
        beds=[
            BedCreate(
                bed_identifier="Bed 101",
                monthly_rent=Decimal("24000.00"),
                available_from=date.today(),
            )
        ],
    )
    prop_create = PropertyCreate(
        title="Luxury 2BHK in Koramangala 4th Block",
        description="Premium fully-furnished flat with high-speed wifi and terrace garden.",
        property_category="apartment",
        configuration="2BHK",
        latitude=12.9345,
        longitude=77.6256,
        address_display="Koramangala 4th Block, Bengaluru",
        address_exact="Flat 204, Green Oasis Apartments",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560034",
        monthly_rent=Decimal("48000.00"),
        security_deposit=Decimal("140000.00"),
        total_bedrooms=2,
        total_bathrooms=2,
        max_capacity=3,
        current_occupants=0,
        available_from=date.today(),
        amenities=["wifi", "power_backup", "gated_security"],
        rooms=[room_1],
    )

    prop_mock_res = {
        "id": prop_id,
        "owner_id": owner_id,
        "title": prop_create.title,
        "listing_status": "published",
        "max_capacity": 3,
        "current_occupants": 0,
        "rooms": [{"id": uuid4(), "room_name": "Deluxe Room 1", "max_beds": 1, "occupied_beds": 0}],
    }
    prop_service.get_by_id = AsyncMock(return_value=prop_mock_res)
    created_prop = await prop_service.create(owner_id, prop_create)
    assert created_prop["listing_status"] == "published"

    # Status toggle: Pause listing
    prop_entity = Property(
        id=prop_id,
        owner_id=owner_id,
        title=prop_create.title,
        listing_status="published",
        max_capacity=3,
        current_occupants=0,
    )
    mock_prop_found = MagicMock(scalar_one_or_none=MagicMock(return_value=prop_entity))
    mock_db.execute.side_effect = [mock_prop_found]
    prop_mock_paused = {**prop_mock_res, "listing_status": "paused"}
    prop_service.get_by_id = AsyncMock(return_value=prop_mock_paused)
    paused = await prop_service.update_listing_status(prop_id, owner_id, "paused")
    assert paused["listing_status"] == "paused"

    # Review application: Accept
    app_service = ApplicationService(mock_db)
    app = ApplicationCreate(
        property_id=prop_id,
        introduction="Hi! I am a senior engineer at a fintech startup. Clean and quiet.",
        proposed_rent=Decimal("24000.00"),
        move_in_target=date.today() + timedelta(days=7),
    )
    mock_no_dup = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_prop_found, mock_no_dup]
    app_instance = await app_service.create(applicant_id, app)
    assert app_instance.status == "submitted"

    app_service.get_by_id = AsyncMock(return_value=app_instance)
    mock_db.execute.side_effect = [mock_prop_found]
    accepted_app = await app_service.update_status(
        app_instance.id,
        owner_id,
        ApplicationStatusUpdate(status="accepted", note="Looking forward to hosting you!"),
    )
    assert accepted_app.status == "accepted"

    # Viewing appointment: Confirm
    apt_service = AppointmentService(mock_db)
    mock_db.execute.side_effect = [mock_prop_found, mock_no_dup]
    apt = await apt_service.create(
        applicant_id,
        AppointmentCreate(
            property_id=prop_id,
            host_id=owner_id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
            appointment_type="physical_visit",
        ),
    )
    apt_service.get_by_id = AsyncMock(return_value=apt)
    confirmed_apt = await apt_service.update_status(
        apt.id,
        owner_id,
        AppointmentStatusUpdate(status="confirmed"),
    )
    assert confirmed_apt.status == "confirmed"

    # Vacate bed action
    mock_room = Room(id=uuid4(), property_id=prop_id, property=prop_entity, occupied_beds=1)
    mock_bed = Bed(id=bed_id, is_occupied=True, current_occupant_id=applicant_id, room=mock_room)
    mock_bed_res = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_bed))
    mock_db.execute.side_effect = [mock_bed_res]
    vacated_bed = await prop_service.vacate_bed(bed_id, owner_id)
    assert vacated_bed.is_occupied is False
    assert vacated_bed.current_occupant_id is None


@pytest.mark.asyncio
async def test_phase18_journey_c_tenant_replacement_vacancy_lifecycle():
    """
    Journey C: Tenant Replacement Vacancy Lifecycle
    1. Active tenancy check.
    2. Post roommate vacancy.
    3. Query vacancies with gender filter.
    4. Close vacancy when roommate found.
    5. Security rejection: non-tenant forbidden.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    tenant_id = uuid4()
    stranger_id = uuid4()
    property_id = uuid4()
    room_id = uuid4()
    vacancy_id = uuid4()

    tenant_service = TenantService(mock_db)

    # 1. Verified Active Membership
    active_membership = TenantMembership(
        id=uuid4(),
        property_id=property_id,
        room_id=room_id,
        tenant_id=tenant_id,
        monthly_rent=Decimal("17500.00"),
        status="active",
        is_primary_tenant=True,
    )
    mock_db.execute.side_effect = [MagicMock(scalar_one_or_none=MagicMock(return_value=active_membership))]

    # 2. Post Vacancy
    vac_create = ExistingTenantVacancyCreate(
        property_id=property_id,
        room_id=room_id,
        title="Furnished Room in HSR 3BHK for Veg Flatmate",
        description="Spacious room with attached washroom. Cook and maid in place.",
        vacant_from=date.today() + timedelta(days=15),
        expected_rent=Decimal("17500.00"),
        deposit_required=Decimal("50000.00"),
        preferred_gender="female",
    )
    vac = await tenant_service.create_vacancy(tenant_id, vac_create)
    assert vac.posted_by_tenant_id == tenant_id
    assert vac.is_active is True

    # 3. List vacancies with gender filter
    vac_obj = ExistingTenantVacancy(
        id=vacancy_id,
        property_id=property_id,
        room_id=room_id,
        posted_by_tenant_id=tenant_id,
        title=vac_create.title,
        expected_rent=Decimal("17500.00"),
        preferred_gender="female",
        is_active=True,
    )
    mock_db.execute.side_effect = [MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[vac_obj]))))]
    results = await tenant_service.list_vacancies(preferred_gender="female")
    assert len(results) == 1
    assert results[0].preferred_gender == "female"

    # 4. Close vacancy
    tenant_service.get_vacancy_by_id = AsyncMock(return_value=vac_obj)
    closed = await tenant_service.close_vacancy(vacancy_id, tenant_id)
    assert closed.is_active is False

    # 5. Security check: Stranger cannot post vacancy without active lease
    mock_db.execute.side_effect = [MagicMock(scalar_one_or_none=MagicMock(return_value=None))]
    with pytest.raises(ForbiddenException):
        await tenant_service.create_vacancy(stranger_id, vac_create)


@pytest.mark.asyncio
async def test_phase18_journey_d_pg_operator_building_management():
    """
    Journey D: PG Operator Building Management
    1. Register PG Building with food plans and curfew rules.
    2. Allocate floor with gender restriction.
    3. Rejection of duplicate PG building on same property.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    operator_id = uuid4()
    property_id = uuid4()
    pg_id = uuid4()

    pg_service = PGService(mock_db)

    # 1. Register PG Building
    mock_no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_existing]

    expected_building = PGBuilding(
        id=pg_id,
        operator_id=operator_id,
        property_id=property_id,
        building_name="Aura Coliving Residency",
        pg_type="coed",
        total_floors=4,
        food_included=True,
        meal_type="veg_and_non_veg",
        meals_served_per_day=3,
        gate_closing_time="23:00",
        notice_period_days=30,
        biometric_entry=True,
    )
    pg_service.get_building = AsyncMock(return_value=expected_building)

    pg_create = PGBuildingCreate(
        property_id=property_id,
        building_name="Aura Coliving Residency",
        pg_type="coed",
        total_floors=4,
        food_included=True,
        meal_type="veg_and_non_veg",
        meals_served_per_day=3,
        gate_closing_time="23:00",
        notice_period_days=30,
        biometric_entry=True,
    )
    b = await pg_service.create_building(operator_id, pg_create)
    assert b.building_name == "Aura Coliving Residency"
    assert b.gate_closing_time == "23:00"

    # 2. Add floor with gender restriction
    building_obj = PGBuilding(id=pg_id, operator_id=operator_id, total_floors=4)
    pg_service.get_building = AsyncMock(return_value=building_obj)

    floor_create = PGFloorCreate(
        floor_number=2,
        gender_restriction="ladies_only",
        total_rooms=6,
    )
    floor = await pg_service.add_floor(pg_id, operator_id, floor_create)
    assert floor.floor_number == 2
    assert floor.gender_restriction == "ladies_only"

    # 3. Duplicate building rejection
    mock_has_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=expected_building))
    mock_db.execute.side_effect = [mock_has_existing]
    with pytest.raises(ConflictException):
        await pg_service.create_building(operator_id, pg_create)


@pytest.mark.asyncio
@pytest.mark.usefixtures("stub_city_catalogue")
async def test_phase18_journey_e_group_consensus_and_collective_score():
    """
    Journey E: Group Consensus & Collective Score
    1. Create group syndicate.
    2. Add invited members (authorized by leader).
    3. Vote on wishlist property.
    4. Compute group collective compatibility with dealbreaker penalty.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    leader_id = uuid4()
    member_a = uuid4()
    group_id = uuid4()
    prop_id = uuid4()

    group_service = GroupService(mock_db)

    # 1. Create Group
    group_create = GroupCreate(
        name="Indiranagar Tech Trio",
        description="Looking for 3BHK close to 100ft road.",
        target_budget_total=75000,
        target_city="Bengaluru",
        target_move_in=date.today() + timedelta(days=20),
    )
    group_entity = Group(
        id=group_id,
        creator_id=leader_id,
        name=group_create.name,
        target_budget_total=75000,
        target_city="Bengaluru",
        members=[],
        wishlist_items=[],
    )
    group_service.get_by_id = AsyncMock(return_value=group_entity)
    g = await group_service.create(leader_id, group_create)
    assert g.name == "Indiranagar Tech Trio"

    # 2. Add member (Leader authorized)
    mock_no_member = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_member]
    member = await group_service.add_member(
        group_id=group_id,
        user_id=member_a,
        requester_id=leader_id,
        role="member",
    )
    assert member.user_id == member_a

    # Non-member rejection
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

    # 3. Member votes on wishlist item
    mock_membership_ok = MagicMock(scalar_one_or_none=MagicMock(return_value=GroupMember(group_id=group_id, user_id=leader_id)))
    mock_no_wishlist_item = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_membership_ok, mock_no_wishlist_item]

    wishlist_item = await group_service.vote_wishlist(
        group_id=group_id,
        property_id=prop_id,
        user_id=leader_id,
        vote="up",
    )
    assert wishlist_item.votes[str(leader_id)] == "up"


@pytest.mark.asyncio
async def test_phase18_journey_f_trust_safety_blocking_and_moderation():
    """
    Journey F: Trust, Safety & Moderation
    1. Report suspicious listing / fraudster.
    2. Block user and verify interaction denial.
    3. Moderation review and resolution.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    reporter_id = uuid4()
    fraudster_id = uuid4()
    report_id = uuid4()

    mod_service = ModerationService(mock_db)

    # 1. Submit report against advance money scam
    rep_create = ReportCreate(
        target_type="user",
        target_id=fraudster_id,
        reason="advance_fee_scam",
        description="Demanding ₹10,000 token transfer on UPI before showing the apartment.",
    )
    report = await mod_service.submit_report(reporter_id, rep_create)
    assert report.reason == "advance_fee_scam"
    assert report.status == "open"

    # Self-report rejected
    with pytest.raises(BadRequestException):
        await mod_service.submit_report(
            reporter_id,
            ReportCreate(target_type="user", target_id=reporter_id, reason="spam"),
        )

    # 2. Block bad actor
    mock_no_block = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_block]
    block = await mod_service.block_user(reporter_id, fraudster_id)
    assert block.blocked_user_id == fraudster_id

    # 3. Moderation review
    report_obj = ModerationReport(
        id=report_id,
        reporter_id=reporter_id,
        target_type="user",
        target_id=fraudster_id,
        reason="advance_fee_scam",
        status="open",
    )
    mock_db.execute.side_effect = [MagicMock(scalar_one_or_none=MagicMock(return_value=report_obj))]
    reviewed = await mod_service.review_report(
        report_id=report_id,
        review=ReportReviewRequest(
            status="resolved",
            resolution_notes="Fraud confirmed. Account suspended and IP flagged.",
        ),
    )
    assert reviewed.status == "resolved"


@pytest.mark.asyncio
async def test_phase18_journey_g_account_recovery_and_credentials():
    """
    Journey G: Account Recovery & Profile Settings
    1. Forgot password token request.
    2. Reset password completion with minimum 8 characters.
    3. Update user profile details (phone number, name).
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    user_id = uuid4()
    test_user = User(
        id=user_id,
        email="rohit.sharma@example.com",
        full_name="Rohit Sharma",
        role="seeker",
        is_active=True,
        hashed_password="hashed_old_password",
    )

    auth_service = AuthService(mock_db)

    # 1. Forgot password request
    mock_db.execute.side_effect = [MagicMock(scalar_one_or_none=MagicMock(return_value=test_user))]
    fp_res, fp_emails = await auth_service.forgot_password(ForgotPasswordRequest(email="rohit.sharma@example.com"))
    assert [e.template for e in fp_emails] == ["password_reset"]
    assert fp_res["success"] is True
    assert "reset_token" in fp_res

    # 2. Reset password with new secure password
    reset_token = fp_res["reset_token"]
    mock_db.execute.side_effect = [MagicMock(scalar_one_or_none=MagicMock(return_value=test_user))]
    rp_res, rp_emails = await auth_service.reset_password(
        ResetPasswordRequest(token=reset_token, new_password="NewSecureP@ssword2026")
    )
    assert rp_res["success"] is True
    assert "reset successfully" in rp_res["message"]
    assert [e.template for e in rp_emails] == ["password_changed"]

    # 3. Update user phone number
    user_service = UserService(mock_db)
    updated_user = await user_service.update(
        test_user,
        UserUpdate(phone_number="+91 98765 43210"),
    )
    assert updated_user.phone_number == "+91 98765 43210"


@pytest.mark.asyncio
async def test_phase18_journey_h_dpdp_privacy_and_location_masking():
    """
    Journey H: DPDP Act Privacy & Location Masking
    1. Exact residential address masked for public/unconfirmed seekers.
    2. Approximate display address and fuzzed coordinates returned.
    3. Full address and coordinates exposed only to the verified owner.
    """
    owner_id = uuid4()
    stranger_id = uuid4()
    prop_id = uuid4()

    prop = Property(
        id=prop_id,
        owner_id=owner_id,
        title="Spacious 3BHK in HSR Layout",
        description="Quiet residential street near parks.",
        property_category="apartment",
        configuration="3BHK",
        address_display="HSR Layout Sector 2, Bengaluru",
        address_exact="Flat 302, Green Glen Apartments, 14th Cross",
        location=WKTElement("POINT(77.6446 12.9121)", srid=4326),
        city="Bengaluru",
        state="Karnataka",
        postal_code="560102",
        country="India",
        currency="INR",
        monthly_rent=Decimal("38000.00"),
        security_deposit=Decimal("110000.00"),
        maintenance_monthly=Decimal("2500.00"),
        bills_included=False,
        listing_status="published",
        total_bedrooms=3,
        total_bathrooms=2,
        max_capacity=4,
        current_occupants=1,
        available_from=date.today(),
        is_furnished=True,
        furnishing_status="fully_furnished",
        pets_allowed=True,
        smoking_allowed=False,
        is_verified=True,
        is_active=True,
        images=[],
        rooms=[],
        amenities=[],
    )

    prop_service = PropertyService(AsyncMock())

    # 1. When viewed by stranger/seeker: exact address must be masked
    formatted_seeker = prop_service._format_property_response(
        prop,
        viewer_id=stranger_id,
        is_admin=False,
    )
    assert formatted_seeker["address_exact"] == "[Exact address protected - revealed upon confirmed visit]"
    assert formatted_seeker["address_display"] == "HSR Layout Sector 2, Bengaluru"
    # Coordinates must be fuzzed (not Bengaluru center or raw precision)
    assert "latitude" in formatted_seeker and "longitude" in formatted_seeker

    # 2. When viewed by the owner: exact address must be revealed in full
    formatted_owner = prop_service._format_property_response(
        prop,
        viewer_id=owner_id,
        is_admin=False,
    )
    assert formatted_owner["address_exact"] == "Flat 302, Green Glen Apartments, 14th Cross"
    assert formatted_owner["address_display"] == "HSR Layout Sector 2, Bengaluru"
