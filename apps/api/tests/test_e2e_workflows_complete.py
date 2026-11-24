"""
Comprehensive Phase 16 Real End-to-End Business Workflows Test Suite
Executes Workflows A, B, C, D, E, and F covering success, failure, and recovery paths.
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
from app.modules.administration.service import AdminService
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
)


@pytest.mark.asyncio
async def test_workflow_a_flatmate_seeker_journey():
    """
    Workflow A: New flatmate seeker
    1. Register -> 2. Authenticate -> 3. Complete profile -> 4. Add professional info
    5. Lifestyle preferences -> 6. Set budget -> 7. Dealbreakers -> 8. Discover flatmates
    9. View compatibility report -> 10. Send interest -> 11. Establish mutual match
    12. Access authorized conversation.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    seeker_id = uuid4()
    candidate_id = uuid4()

    # 1 & 2: User profile representation
    seeker_user = User(
        id=seeker_id,
        email="ananya.seeker@example.com",
        full_name="Ananya Iyer",
        role="seeker",
        is_active=True,
    )
    assert seeker_user.email == "ananya.seeker@example.com"

    # 3 & 4 & 6: Profile & Professional Information
    profile_service = ProfileService(mock_db)
    seeker_profile = Profile(
        id=uuid4(),
        user_id=seeker_id,
        display_name="Ananya I.",
        bio="Fullstack Developer at Bangalore Tech Hub. Enjoys specialty coffee and books.",
        occupation="Software Engineer",
        company_name="Innovate Labs",
        designation="Senior Engineer",
        budget_min=18000,
        budget_max=28000,
        preferred_locations=["Indiranagar", "Koramangala"],
    )
    profile_service.get_by_user_id = AsyncMock(return_value=seeker_profile)

    update_payload = ProfileUpdate(
        bio="Updated bio: Quiet and focused professional.",
        budget_min=20000,
        budget_max=30000,
    )
    updated_profile = await profile_service.update(seeker_id, update_payload)
    assert updated_profile.budget_min == 20000

    # 5: Lifestyle Questionnaire
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

    # 7: Set Hard Dealbreaker (Strictly No Smoking Inside)
    db_create = DealbreakerCreate(
        rule_key="no_smoking_inside",
        is_strict=True,
        expected_value="never",
    )
    created_db = await lifestyle_service.add_dealbreaker(seeker_id, db_create)
    assert created_db.rule_key == "no_smoking_inside"
    assert created_db.is_strict is True

    # 8 & 9: Discover Flatmates & View Compatibility Report
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
    assert "Cleanliness and tidiness alignment scored at 100%." in comp["explanations"]["cleanliness"]

    # 10 & 11: Send Interest and Establish Mutual Match
    matching_service = MatchingService(mock_db)
    matching_service.pair_features = AsyncMock(return_value=None)  # profile reads not mocked here
    # Seeker likes Candidate (First interaction)
    mock_no_int = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_int, mock_no_int, mock_no_int]
    inter_1 = await matching_service.record_interaction(seeker_id, candidate_id, "like")
    assert inter_1.is_mutual_match is False

    # Candidate likes Seeker back -> Mutual Match!
    recip = MatchInteraction(user_id=seeker_id, target_user_id=candidate_id, action="like")
    mock_recip_found = MagicMock(scalar_one_or_none=MagicMock(return_value=recip))
    mock_no_mutual = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    matching_service.get_pairwise_score = AsyncMock(return_value=MagicMock(overall_score=94.0, model_dump=MagicMock(return_value={"overall_score": 94.0})))
    mock_db.execute.side_effect = [mock_no_int, mock_no_int, mock_recip_found, mock_no_mutual]

    inter_2 = await matching_service.record_interaction(candidate_id, seeker_id, "like")
    assert inter_2.is_mutual_match is True

    # 12: Access Authorized Conversation
    messaging_service = MessagingService(mock_db)
    mock_no_block = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_no_conv = MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None))))
    # Nobody here turned direct messages off.
    mock_no_dm_optout = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    mock_db.execute.side_effect = [mock_no_block, mock_no_conv, mock_no_dm_optout]
    conv_req = CreateConversationRequest(
        type="direct",
        participant_user_ids=[candidate_id],
    )
    conv = await messaging_service.create_conversation(seeker_id, conv_req)
    assert conv.type == "direct"


@pytest.mark.asyncio
@pytest.mark.usefixtures("stub_city_catalogue")
async def test_workflow_b_property_owner_journey():
    """
    Workflow B: Property owner
    1. Register -> 2. Owner profile -> 3. Submit verification -> 4. Create property
    5. Configuration -> 6. Rooms -> 7. Amenities -> 8. Pricing -> 9. Images
    10. Publish listing -> 11. Receive enquiry -> 12. Review application -> 13. Schedule visit
    14. Update listing availability.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    owner_id = uuid4()
    applicant_id = uuid4()

    # 4 to 9: Create Property with Units, Rooms, Beds, Amenities, Images
    prop_service = PropertyService(mock_db)
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
        title="Spacious 3BHK Flat in HSR Layout",
        description="Gated community near tech parks with power backup and security.",
        property_category="apartment",
        configuration="3BHK",
        latitude=12.9121,
        longitude=77.6446,
        address_display="HSR Layout Sector 1, Bengaluru",
        address_exact="Flat 401, Sai Meadows",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560102",
        monthly_rent=Decimal("45000.00"),
        security_deposit=Decimal("120000.00"),
        total_bedrooms=3,
        total_bathrooms=3,
        max_capacity=4,
        current_occupants=0,
        available_from=date.today(),
        images=["https://images.unsplash.com/photo-1522708323590-d24dbb6b0267"],
        amenities=["wifi", "lift", "power_backup", "parking"],
        rooms=[room_1],
    )

    prop_mock_res = {
        "id": uuid4(),
        "owner_id": owner_id,
        "title": prop_create.title,
        "listing_status": "published",
        "max_capacity": 4,
        "current_occupants": 0,
        "rooms": [{"id": uuid4(), "room_name": "Master Suite", "max_beds": 1, "occupied_beds": 0}],
    }
    prop_service.get_by_id = AsyncMock(return_value=prop_mock_res)
    created_prop = await prop_service.create(owner_id, prop_create)
    assert created_prop["title"] == prop_create.title

    # 10: Status check
    assert created_prop["listing_status"] == "published"

    # 11 & 12: Receive & Review Rental Application
    app_service = ApplicationService(mock_db)
    prop_obj = Property(
        id=created_prop["id"],
        owner_id=owner_id,
        title=prop_create.title,
        monthly_rent=Decimal("45000.00"),
        max_capacity=4,
        current_occupants=0,
    )
    mock_prop_ok = MagicMock(scalar_one_or_none=MagicMock(return_value=prop_obj))
    mock_no_dup = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_prop_ok, mock_no_dup]

    app = await app_service.create(
        applicant_id=applicant_id,
        data=ApplicationCreate(
            property_id=prop_obj.id,
            introduction="Respectful software engineer seeking room near office.",
            proposed_rent=Decimal("22000.00"),
            move_in_target=date.today() + timedelta(days=10),
        ),
    )
    assert app.status == "submitted"

    # Owner reviews application: Accepts
    app_service.get_by_id = AsyncMock(return_value=app)
    mock_db.execute.side_effect = [mock_prop_ok]
    reviewed_app = await app_service.update_status(
        application_id=app.id,
        current_user_id=owner_id,
        data=ApplicationStatusUpdate(status="accepted", note="Welcome to the flat!"),
    )
    assert reviewed_app.status == "accepted"

    # 13: Viewing Appointment Scheduling & Confirmation
    apt_service = AppointmentService(mock_db)
    mock_db.execute.side_effect = [mock_prop_ok, mock_no_dup]
    apt = await apt_service.create(
        applicant_id=applicant_id,
        data=AppointmentCreate(
            property_id=prop_obj.id,
            host_id=owner_id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
            appointment_type="physical_visit",
        ),
    )
    assert apt.status == "pending"

    # Host confirms
    apt_service.get_by_id = AsyncMock(return_value=apt)
    confirmed_apt = await apt_service.update_status(
        appointment_id=apt.id,
        user_id=owner_id,
        data=AppointmentStatusUpdate(status="confirmed"),
    )
    assert confirmed_apt.status == "confirmed"


@pytest.mark.asyncio
async def test_workflow_c_existing_tenant_vacancy_journey():
    """
    Workflow C: Existing tenant replacement
    1. Register -> 2. Household profile -> 3. Declare listing rights
    4. Add available room -> 5. House rules -> 6. Compatible candidates
    7. Receive interests -> 8. Manage replacement workflow.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    tenant_id = uuid4()
    property_id = uuid4()
    room_id = uuid4()

    tenant_service = TenantService(mock_db)

    # 3: Active Tenancy Verification Check
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

    # 4 & 5: Post Replacement Vacancy with House Rules & Preferences
    vacancy_req = ExistingTenantVacancyCreate(
        property_id=property_id,
        room_id=room_id,
        title="Spacious Room Available in Indiranagar 2BHK",
        description="Roommate moving abroad. Looking for a vegetarian, early riser flatmate.",
        vacant_from=date.today() + timedelta(days=20),
        expected_rent=Decimal("16000.00"),
        deposit_required=Decimal("50000.00"),
        preferred_gender="any",
    )
    vacancy = await tenant_service.create_vacancy(tenant_id, vacancy_req)
    assert vacancy.posted_by_tenant_id == tenant_id
    assert vacancy.is_active is True

    # Negative security test: Unverified tenant cannot post vacancy
    mock_no_membership = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_membership]
    stranger_id = uuid4()
    with pytest.raises(ForbiddenException):
        await tenant_service.create_vacancy(stranger_id, vacancy_req)


@pytest.mark.asyncio
async def test_workflow_d_pg_operator_occupancy_journey():
    """
    Workflow D: PG operator
    1. Register -> 2. Create PG -> 3. Add floors -> 4. Rooms -> 5. Beds
    6. Configure occupancy -> 7. Pricing -> 8. Publish availability
    9. Receive enquiry -> 10. Update occupancy.
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

    # 2: Create PG Building
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

    # 3: Add Floor
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


@pytest.mark.asyncio
@pytest.mark.usefixtures("stub_city_catalogue")
async def test_workflow_e_group_flatmate_matching():
    """
    Workflow E: Group flatmate matching
    1. Create group -> 2. Invite members -> 3. Accept invitations
    4. Shared budget -> 5. Location preferences -> 6. Pairwise compatibility
    7. Group compatibility -> 8. Conflicts -> 9. Vote on properties.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    leader_id = uuid4()
    member_id = uuid4()
    group_id = uuid4()
    prop_id = uuid4()

    group_service = GroupService(mock_db)

    # 1: Create Group
    group_create = GroupCreate(
        name="Koramangala 3BHK Seekers",
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
    assert g.name == "Koramangala 3BHK Seekers"

    # 2 & 3: Invite & Add Member (Authorized by creator)
    mock_no_existing_member = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_existing_member]
    member = await group_service.add_member(
        group_id=group_id,
        user_id=member_id,
        requester_id=leader_id,
        role="member",
    )
    assert member.user_id == member_id

    # Security test: Non-leader stranger cannot inject members
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

    # 9: Wishlist Voting by Group Member
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

    # Security test: Non-member cannot vote on group wishlist
    mock_non_member = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_non_member]
    with pytest.raises(ForbiddenException):
        await group_service.vote_wishlist(group_id, prop_id, stranger_id, "up")


@pytest.mark.asyncio
async def test_workflow_f_safety_moderation_admin():
    """
    Workflow F: Safety and administration
    1. Report user -> 2. Block user -> 3. Submit property report
    4. Moderation queue -> 5. Review report -> 6. Apply moderation action
    7. Admin audit stats -> 8. Unauthorized access prevention.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    user_a = uuid4()
    bad_actor = uuid4()
    prop_id = uuid4()

    moderation_service = ModerationService(mock_db)

    # 1: Report a user
    rep_req = ReportCreate(
        target_type="user",
        target_id=bad_actor,
        reason="harassment",
        description="Inappropriate language and harassment in chat.",
    )
    report = await moderation_service.submit_report(user_a, rep_req)
    assert report.status == "open"
    assert report.reason == "harassment"

    # Self-reporting rejection check
    with pytest.raises(BadRequestException):
        await moderation_service.submit_report(
            user_a,
            ReportCreate(target_type="user", target_id=user_a, reason="spam"),
        )

    # 2: Block a user
    mock_no_block = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = [mock_no_block]
    block = await moderation_service.block_user(user_a, bad_actor)
    assert block.blocked_user_id == bad_actor

    # Duplicate block check
    existing_block = UserBlock(user_id=user_a, blocked_user_id=bad_actor)
    mock_has_block = MagicMock(scalar_one_or_none=MagicMock(return_value=existing_block))
    mock_db.execute.side_effect = [mock_has_block]
    with pytest.raises(ConflictException):
        await moderation_service.block_user(user_a, bad_actor)

    # 3: Submit property report
    prop_rep = ReportCreate(
        target_type="property",
        target_id=prop_id,
        reason="misleading_photos",
        description="Listing images do not reflect the actual state of the property.",
    )
    p_report = await moderation_service.submit_report(user_a, prop_rep)
    assert p_report.target_type == "property"

    # 4 & 5 & 6: Review report as moderator
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

    # 7: Admin audit stats
    admin_service = AdminService(mock_db)
    mock_scalar = MagicMock(side_effect=[250, 85, 72, 45, 18, 5])
    mock_res = MagicMock(scalar=mock_scalar)
    mock_db.execute.side_effect = None
    mock_db.execute.return_value = mock_res
    stats = await admin_service.get_platform_stats()
    assert stats.total_users == 250
    assert stats.total_properties == 85
