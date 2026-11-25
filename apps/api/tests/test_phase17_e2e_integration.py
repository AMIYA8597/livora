"""
Phase 17 Comprehensive End-to-End Real Persistence Integration Test Suite
Executes complete business workflows against real PostgreSQL database and verifies
full frontend-backend contract fulfillment.
"""
import pytest
from tests.image_samples import make_image
from uuid import uuid4, UUID
from decimal import Decimal
from datetime import datetime, timezone, timedelta, date

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import AsyncSessionLocal
from sqlalchemy import select

from app.modules.tenants.models import TenantMembership
from app.modules.properties.models import Room
from app.modules.users.models import User
from app.modules.users.privacy import purge_account
from app.modules.administration.service import AdminService


@pytest.fixture
async def created_accounts():
    """
    Emails the test registers. Their accounts are erased afterwards (listings and files too),
    so repeated local runs don't pile up listings that crowd other tests' location searches.
    """
    emails: list = []
    yield emails
    async with AsyncSessionLocal() as s:
        user_ids = (await s.execute(select(User.id).where(User.email.in_(emails)))).scalars().all()
        for user_id in user_ids:
            await purge_account(s, user_id)


@pytest.mark.asyncio
async def test_complete_phase17_end_to_end_integration(created_accounts):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # -------------------------------------------------------------
        # 1. User Registration & Lifecycle: Seeker & Owner
        # -------------------------------------------------------------
        seeker_email = f"seeker_{uuid4().hex[:8]}@example.in"
        owner_email = f"owner_{uuid4().hex[:8]}@example.in"
        created_accounts.extend([seeker_email, owner_email])
        password = "SecurePassword123!"

        # Register Seeker
        res_seeker_reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": seeker_email,
                "password": password,
                "full_name": "Pooja Sharma",
                "role": "seeker",
                "phone_number": "+919876543210",
            },
        )
        assert res_seeker_reg.status_code == 201, res_seeker_reg.text
        seeker_data = res_seeker_reg.json()
        seeker_id = seeker_data["user"]["id"]
        seeker_token = seeker_data["access_token"]
        seeker_headers = {"Authorization": f"Bearer {seeker_token}"}

        # Register Owner
        res_owner_reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": owner_email,
                "password": password,
                "full_name": "Rajesh Landlord",
                "role": "owner",
                "phone_number": "+919876543211",
            },
        )
        assert res_owner_reg.status_code == 201, res_owner_reg.text
        owner_data = res_owner_reg.json()
        owner_id = owner_data["user"]["id"]
        owner_token = owner_data["access_token"]
        owner_headers = {"Authorization": f"Bearer {owner_token}"}

        # Verify Token Refresh
        res_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": seeker_data["refresh_token"]},
        )
        assert res_refresh.status_code == 200, res_refresh.text

        # -------------------------------------------------------------
        # 2. Profile Management & 10-Dimension Lifestyle & Dealbreakers
        # -------------------------------------------------------------
        res_prof_update = await client.put(
            "/api/v1/profiles/me",
            headers=seeker_headers,
            json={
                "display_name": "Pooja S.",
                "bio": "Senior UX Designer at Whitefield tech park. Loves clean spaces and quiet mornings.",
                "occupation": "Senior UX Designer",
                "budget_min": 15000,
                "budget_max": 25000,
                "preferred_locations": ["Indiranagar", "HSR Layout"],
            },
        )
        assert res_prof_update.status_code == 200, res_prof_update.text
        assert res_prof_update.json()["display_name"] == "Pooja S."

        # Submit 10-Dimension Lifestyle
        res_lifestyle = await client.put(
            "/api/v1/lifestyle/me",
            headers=seeker_headers,
            json={
                "sleep_schedule": "early_bird",
                "cleanliness_level": 5,
                "work_arrangement": "hybrid",
                "diet_preference": "vegetarian",
                "smoking": "never",
                "pet_preference": "cats_and_dogs_ok",
                "social_battery": "balanced",
                "noise_tolerance": "moderate",
                "guests_policy": "occasional_weekends",
            },
        )
        assert res_lifestyle.status_code == 200, res_lifestyle.text
        assert res_lifestyle.json()["cleanliness_level"] == 5

        # Add Dealbreaker
        res_dealbreaker = await client.post(
            "/api/v1/lifestyle/dealbreakers",
            headers=seeker_headers,
            json={
                "rule_key": "no_smoking_inside",
                "is_strict": True,
                "expected_value": "never",
            },
        )
        assert res_dealbreaker.status_code == 201, res_dealbreaker.text
        db_id = res_dealbreaker.json()["id"]

        # Fetch Dealbreakers
        res_get_dbs = await client.get("/api/v1/lifestyle/dealbreakers", headers=seeker_headers)
        assert res_get_dbs.status_code == 200
        assert any(d["id"] == db_id for d in res_get_dbs.json())

        # Privacy Settings
        res_privacy = await client.put(
            "/api/v1/profiles/me/privacy",
            headers=seeker_headers,
            json={
                "show_phone_publicly": False,
                "allow_direct_messages": True,
            },
        )
        assert res_privacy.status_code == 200, res_privacy.text
        assert res_privacy.json()["show_phone_publicly"] is False

        # -------------------------------------------------------------
        # 3. Storage Upload & Signed URL
        # -------------------------------------------------------------
        res_upload = await client.post(
            "/api/v1/storage/upload",
            headers=seeker_headers,
            files={"file": ("avatar.png", make_image("PNG"), "image/png")},
            data={"bucket": "avatars"},
        )
        assert res_upload.status_code == 201, res_upload.text
        file_url = res_upload.json()["file_url"]
        assert "avatars" in file_url

        # -------------------------------------------------------------
        # 4. Property Listing (Owner Role)
        # -------------------------------------------------------------
        res_prop = await client.post(
            "/api/v1/properties/",
            headers=owner_headers,
            json={
                "title": "Sunlit 3BHK Flat in HSR Layout",
                "description": "Spacious flat with dedicated power backup, covered parking, and high-speed fiber.",
                "property_category": "apartment",
                "configuration": "3BHK",
                "latitude": 12.9121,
                "longitude": 77.6446,
                "address_display": "HSR Layout Sector 2, Bengaluru",
                "address_exact": "Flat 301, Sunshine Heights, 19th Main Road",
                "city": "Bengaluru",
                "postal_code": "560102",
                "country": "India",
                "currency": "INR",
                "monthly_rent": 36000.0,
                "security_deposit": 100000.0,
                "total_bedrooms": 3,
                "total_bathrooms": 3,
                "available_from": date.today().isoformat(),
                "is_furnished": True,
                "furnishing_status": "semi_furnished",
                "pets_allowed": True,
                "smoking_allowed": False,
                "images": ["https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800"],
                "amenities": ["wifi", "power_backup", "security", "lift"],
            },
        )
        assert res_prop.status_code == 201, res_prop.text
        prop_id = res_prop.json()["id"]

        # Search properties
        res_search_prop = await client.get("/api/v1/properties", params={"city": "Bengaluru", "max_rent": 40000})
        assert res_search_prop.status_code == 200
        assert len(res_search_prop.json()) >= 1

        # -------------------------------------------------------------
        # 5. Matching & Interactions
        # -------------------------------------------------------------
        # Owner also fills a lifestyle profile for compatibility
        await client.put(
            "/api/v1/lifestyle/me",
            headers=owner_headers,
            json={
                "sleep_schedule": "early_bird",
                "cleanliness_level": 4,
                "work_arrangement": "office",
                "diet_preference": "vegetarian",
                "smoking": "never",
                "pet_preference": "cats_and_dogs_ok",
                "social_battery": "balanced",
                "noise_tolerance": "moderate",
                "guests_policy": "occasional_weekends",
            },
        )

        # Seeker computes compatibility with Owner
        res_compat = await client.get(f"/api/v1/matching/compatibility/{owner_id}", headers=seeker_headers)
        assert res_compat.status_code == 200, res_compat.text
        compat_data = res_compat.json()
        assert "overall_score" in compat_data
        assert compat_data["overall_score"] > 0

        # Seeker Likes Owner
        res_like1 = await client.post(
            "/api/v1/matching/interactions",
            headers=seeker_headers,
            json={"target_user_id": owner_id, "action": "like"},
        )
        assert res_like1.status_code == 200, res_like1.text

        # Owner Likes Seeker back -> Mutual Match!
        res_like2 = await client.post(
            "/api/v1/matching/interactions",
            headers=owner_headers,
            json={"target_user_id": seeker_id, "action": "like"},
        )
        assert res_like2.status_code == 200, res_like2.text
        assert res_like2.json()["is_mutual_match"] is True

        # Fetch Mutual Matches for Seeker
        res_mutual = await client.get("/api/v1/matching/matches", headers=seeker_headers)
        assert res_mutual.status_code == 200
        assert len(res_mutual.json()) >= 1

        # -------------------------------------------------------------
        # 6. Team-Up Groups & Wishlist Voting
        # -------------------------------------------------------------
        res_group = await client.post(
            "/api/v1/groups/",
            headers=seeker_headers,
            json={
                "name": "HSR Bangalore Tech Syndicate",
                "description": "Looking to team up for a 3BHK flat near tech parks.",
                "target_city": "Bengaluru",
                "target_budget_total": 60000,
                "target_move_in": date.today().isoformat(),
            },
        )
        assert res_group.status_code == 201, res_group.text
        group_id = res_group.json()["id"]

        # Add Owner to Group
        res_add_member = await client.post(
            f"/api/v1/groups/{group_id}/members",
            headers=seeker_headers,
            json={"user_id": owner_id, "role": "member"},
        )
        assert res_add_member.status_code == 201, res_add_member.text

        # Vote on Wishlist
        res_vote = await client.post(
            f"/api/v1/groups/{group_id}/wishlist/{prop_id}/vote",
            headers=seeker_headers,
            json={"vote": "up"},
        )
        assert res_vote.status_code == 200, res_vote.text
        assert res_vote.json()["votes"].get(seeker_id) == "up"

        # Compute Group Compatibility
        res_grp_compat = await client.get(f"/api/v1/groups/{group_id}/compatibility", headers=seeker_headers)
        assert res_grp_compat.status_code == 200, res_grp_compat.text
        assert "collective_score" in res_grp_compat.json()

        # -------------------------------------------------------------
        # 7. Tenancy Applications & Owner Review
        # -------------------------------------------------------------
        res_app = await client.post(
            "/api/v1/applications/",
            headers=seeker_headers,
            json={
                "property_id": prop_id,
                "proposed_rent": 35000.0,
                "move_in_target": (date.today() + timedelta(days=15)).isoformat(),
                "introduction": "Hello Rajesh, I loved the HSR listing and would love to move in next month.",
            },
        )
        assert res_app.status_code == 201, res_app.text
        app_id = res_app.json()["id"]

        # Owner views received applications
        res_owner_apps = await client.get("/api/v1/owners/applications", headers=owner_headers)
        assert res_owner_apps.status_code == 200, res_owner_apps.text
        assert any(a["application"]["id"] == app_id for a in res_owner_apps.json())

        # Owner approves application
        res_app_status = await client.patch(
            f"/api/v1/applications/{app_id}/status",
            headers=owner_headers,
            json={"status": "approved"},
        )
        assert res_app_status.status_code == 200, res_app_status.text
        assert res_app_status.json()["status"] == "approved"

        # -------------------------------------------------------------
        # 8. Viewing Appointments
        # -------------------------------------------------------------
        scheduled_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        res_apt = await client.post(
            "/api/v1/appointments/",
            headers=seeker_headers,
            json={
                "property_id": prop_id,
                "host_id": owner_id,
                "appointment_type": "physical_visit",
                "scheduled_at": scheduled_at,
                "notes": "Walkthrough on Saturday morning at 11am.",
            },
        )
        assert res_apt.status_code == 201, res_apt.text
        apt_id = res_apt.json()["id"]

        # Cancel appointment
        res_cancel_apt = await client.patch(
            f"/api/v1/appointments/{apt_id}/status",
            headers=seeker_headers,
            json={"status": "cancelled"},
        )
        assert res_cancel_apt.status_code == 200, res_cancel_apt.text
        assert res_cancel_apt.json()["status"] == "cancelled"

        # -------------------------------------------------------------
        # 9. Direct Messaging & Scam Defense Checks
        # -------------------------------------------------------------
        res_conv = await client.post(
            "/api/v1/messaging/conversations",
            headers=seeker_headers,
            json={
                "participant_user_ids": [owner_id],
                "type": "direct",
                "property_id": prop_id,
            },
        )
        assert res_conv.status_code == 201, res_conv.text
        conv_id = res_conv.json()["conversation_id"]

        # Send Message
        res_msg = await client.post(
            "/api/v1/messaging/messages",
            headers=seeker_headers,
            json={
                "conversation_id": conv_id,
                "content": "Hi Rajesh, I am interested in viewing the apartment.",
                "message_type": "text",
            },
        )
        assert res_msg.status_code == 201, res_msg.text
        assert res_msg.json()["content"] == "Hi Rajesh, I am interested in viewing the apartment."

        # Fetch messages in conversation
        res_msgs = await client.get(f"/api/v1/messaging/conversations/{conv_id}/messages", headers=owner_headers)
        assert res_msgs.status_code == 200
        assert len(res_msgs.json()) >= 1

        # -------------------------------------------------------------
        # 10. Tenant Replacement Vacancy & PG Operations
        # -------------------------------------------------------------
        # Seed active tenant membership so seeker can list a vacancy on the property
        async with AsyncSessionLocal() as session:
            room = Room(
                property_id=UUID(prop_id),
                room_name="Master Bedroom",
                room_type="private",
                room_rent=Decimal("15000.00"),
                deposit=Decimal("35000.00"),
                private_bath=True,
                attached_balcony=True,
                max_beds=1,
                occupied_beds=0,
                is_available=True,
                available_from=date.today(),
            )
            session.add(room)
            await session.flush()
            real_room_id = str(room.id)

            membership = TenantMembership(
                property_id=UUID(prop_id),
                room_id=room.id,
                tenant_id=UUID(seeker_id),
                lease_start=date.today(),
                monthly_rent=Decimal("35000.00"),
                status="active",
                is_primary_tenant=True,
            )
            session.add(membership)
            await session.commit()

        res_vac = await client.post(
            "/api/v1/tenants/vacancies",
            headers=seeker_headers,
            json={
                "property_id": prop_id,
                "room_id": real_room_id,
                "title": "Master Bedroom opening in HSR flat",
                "description": "Looking for a vegetarian flatmate to replace current tenant moving to Hyderabad.",
                "vacant_from": (date.today() + timedelta(days=30)).isoformat(),
                "expected_rent": 12000.0,
                "deposit_required": 35000.0,
                "preferred_gender": "any",
            },
        )
        assert res_vac.status_code == 201, res_vac.text
        assert float(res_vac.json()["expected_rent"]) == 12000.0

        # PG Building registration
        res_pg = await client.post(
            "/api/v1/pg/buildings",
            headers=owner_headers,
            json={
                "property_id": prop_id,
                "building_name": "Stanza Green PG Residency",
                "pg_type": "coed",
                "total_floors": 4,
                "food_included": True,
                "meal_type": "veg_and_non_veg",
                "meals_served_per_day": 3,
                "gate_closing_time": "22:30",
                "notice_period_days": 30,
                "biometric_entry": True,
            },
        )
        assert res_pg.status_code == 201, res_pg.text
        pg_id = res_pg.json()["id"]

        # Add floor to PG
        res_floor = await client.post(
            f"/api/v1/pg/buildings/{pg_id}/floors",
            headers=owner_headers,
            json={
                "floor_number": 1,
                "gender_restriction": "female_only",
                "total_rooms": 6,
            },
        )
        assert res_floor.status_code == 201, res_floor.text

        # -------------------------------------------------------------
        # 11. Moderation & Administration
        # -------------------------------------------------------------
        res_report = await client.post(
            "/api/v1/moderation/reports",
            headers=seeker_headers,
            json={
                "target_type": "user",
                "target_id": owner_id,
                "reason": "suspicious_request",
                "description": "Asked for off-platform communication.",
            },
        )
        assert res_report.status_code == 201, res_report.text
        report_id = res_report.json()["id"]

        # Admin user to review report and platform stats. Nobody can sign up as staff, so the
        # account signs up as a seeker and is appointed the way the first one is (grant_role.py).
        admin_email = f"admin_{uuid4().hex[:8]}@example.in"
        created_accounts.append(admin_email)
        res_admin_reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": admin_email,
                "password": password,
                "full_name": "Platform Super Admin",
                "role": "seeker",
                "phone_number": "+919999999999",
            },
        )
        assert res_admin_reg.status_code == 201, res_admin_reg.text
        async with AsyncSessionLocal() as s:
            await AdminService(s).grant_user_role(UUID(res_admin_reg.json()["user"]["id"]), "admin")
        admin_token = res_admin_reg.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Admin fetches platform stats
        res_stats = await client.get("/api/v1/admin/stats", headers=admin_headers)
        assert res_stats.status_code == 200, res_stats.text
        assert res_stats.json()["total_users"] >= 2

        # Admin reviews moderation report
        res_review = await client.patch(
            f"/api/v1/moderation/reports/{report_id}",
            headers=admin_headers,
            json={
                "status": "resolved",
                "action_taken": "User given warning regarding safe communication guidelines.",
            },
        )
        assert res_review.status_code == 200, res_review.text
        assert res_review.json()["status"] == "resolved"

        # -------------------------------------------------------------
        # 12. Password Recovery Journey (Forgot & Reset Password)
        # -------------------------------------------------------------
        res_forgot = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": seeker_email},
        )
        assert res_forgot.status_code == 200, res_forgot.text
        forgot_data = res_forgot.json()
        assert forgot_data["success"] is True
        reset_token = forgot_data.get("reset_token")
        assert reset_token is not None, "Reset token must be returned in test/dev environment"

        new_password = "EvenMoreSecurePassword456!"
        res_reset = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "new_password": new_password},
        )
        assert res_reset.status_code == 200, res_reset.text
        assert res_reset.json()["success"] is True

        # Verify login with new password succeeds
        res_login_new = await client.post(
            "/api/v1/auth/login",
            json={"email": seeker_email, "password": new_password},
        )
        assert res_login_new.status_code == 200, res_login_new.text
        assert "access_token" in res_login_new.json()
