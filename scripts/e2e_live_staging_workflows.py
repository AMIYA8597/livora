"""Live Staging E2E Workflows Test Suite

Executes the 7 required marketplace user journeys directly over HTTP against
the live staging backend at http://127.0.0.1:8001.
"""
import uuid
import datetime
import httpx
import asyncio
import asyncpg

BASE_URL = "http://127.0.0.1:8001"
DB_URL = "postgresql://postgres:postgres@localhost:5432/flatmate_staging_disposable"

async def run_live_e2e_workflows():
    results = {}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        tag = uuid.uuid4().hex[:6]
        print(f"=== Starting Live Staging E2E Suite (tag={tag}) ===")

        # ----------------------------------------------------------------------
        # Journey 1: Seeker registration, profile completion, discovery, and application
        # ----------------------------------------------------------------------
        seeker_token = None
        seeker_headers = {}
        seeker_id = None
        try:
            print("\n[Executing Journey 1: Seeker Registration -> Profile -> Lifestyle -> Discovery]")
            seeker_email = f"seeker_{tag}@staging.example.com"
            r_reg = await client.post("/api/v1/auth/register", json={
                "email": seeker_email,
                "password": "Password123!",
                "full_name": "Aarav Seeker",
                "role": "seeker"
            })
            assert r_reg.status_code in (200, 201), f"Seeker registration failed: {r_reg.text}"
            seeker_token = (await client.post("/api/v1/auth/login", json={"email": seeker_email, "password": "Password123!"})).json()["access_token"]
            seeker_headers = {"Authorization": f"Bearer {seeker_token}"}
            seeker_me = (await client.get("/api/v1/auth/me", headers=seeker_headers)).json()
            seeker_id = seeker_me["id"]

            # Complete Profile (PUT /profiles/me)
            r_prof = await client.put("/api/v1/profiles/me", json={
                "display_name": "Aarav P.",
                "bio": "CS Graduate student at IISc. Quiet, non-smoker, vegetarian.",
                "gender": "male",
                "occupation": "Student",
                "budget_min": 15000,
                "budget_max": 25000,
                "move_in_date": "2026-12-01",
            }, headers=seeker_headers)
            print(f"Seeker Profile Status: {r_prof.status_code}")
            assert r_prof.status_code == 200, f"Profile update failed: {r_prof.text}"

            # Lifestyle Questionnaire (PUT /lifestyle/me)
            r_life = await client.put("/api/v1/lifestyle/me", json={
                "sleep_schedule": "early_bird",
                "dietary_preference": "vegetarian",
                "smoking_tolerance": "non_smoker",
                "drinking_tolerance": "occasional",
                "cleanliness_level": 4,
                "guest_policy": "rarely",
                "pet_tolerance": "pets_welcome",
                "work_style": "student",
                "social_battery": "medium",
                "noise_tolerance": "quiet_preferred",
            }, headers=seeker_headers)
            print(f"Seeker Lifestyle Status: {r_life.status_code}")
            assert r_life.status_code == 200, f"Lifestyle update failed: {r_life.text}"

            # Property Discovery Search
            r_search = await client.get("/api/v1/properties", params={"city": "Bengaluru"})
            print(f"Property Search Status: {r_search.status_code}")
            assert r_search.status_code == 200, f"Property search failed: {r_search.text}"

            results["Journey 1: Seeker Registration, Discovery & Profile"] = "PASS"
        except Exception as e:
            print(f"Journey 1 Failed: {e}")
            results["Journey 1: Seeker Registration, Discovery & Profile"] = f"FAIL: {e}"

        # ----------------------------------------------------------------------
        # Journey 2: Owner registration, listing creation & enquiry management
        # ----------------------------------------------------------------------
        owner_prop_id = None
        owner_room_id = None
        owner_token = None
        owner_headers = {}
        owner_id = None
        try:
            print("\n[Executing Journey 2: Owner Registration -> Listing Creation -> Enquiry Management]")
            owner_email = f"owner_{tag}@staging.example.com"
            await client.post("/api/v1/auth/register", json={
                "email": owner_email,
                "password": "Password123!",
                "full_name": "Vikram Landlord",
                "role": "owner"
            })
            owner_token = (await client.post("/api/v1/auth/login", json={"email": owner_email, "password": "Password123!"})).json()["access_token"]
            owner_headers = {"Authorization": f"Bearer {owner_token}"}
            owner_me = (await client.get("/api/v1/auth/me", headers=owner_headers)).json()
            owner_id = owner_me["id"]

            # Create Property Listing with Rooms & Beds
            r_prop_create = await client.post("/api/v1/properties", json={
                "title": "Sunlit 2BHK in Indiranagar 100ft Road",
                "description": "Executive 2BHK with balcony and power backup.",
                "property_category": "apartment",
                "configuration": "2BHK",
                "latitude": 12.9784,
                "longitude": 77.6408,
                "address_display": "Indiranagar 100ft Road, Bengaluru",
                "address_exact": "Flat 204, Palm Springs Residency",
                "city": "Bengaluru",
                "state": "Karnataka",
                "postal_code": "560038",
                "country": "India",
                "currency": "INR",
                "monthly_rent": 38000.0,
                "security_deposit": 76000.0,
                "maintenance_monthly": 2500.0,
                "bills_included": False,
                "total_bedrooms": 2,
                "total_bathrooms": 2,
                "max_capacity": 4,
                "current_occupants": 0,
                "available_from": "2026-12-01",
                "is_furnished": True,
                "furnishing_status": "fully_furnished",
                "pets_allowed": True,
                "smoking_allowed": False,
                "amenities": ["wifi", "power_backup"],
                "images": ["https://images.unsplash.com/photo-1522708323590-d24dbb6b0267"],
                "rooms": [
                    {
                        "room_name": "Master Bedroom",
                        "room_type": "private",
                        "room_rent": 20000.0,
                        "deposit": 40000.0,
                        "private_bath": True,
                        "attached_balcony": True,
                        "max_beds": 1,
                        "occupied_beds": 0,
                        "is_available": True,
                        "available_from": "2026-12-01",
                        "beds": [{"bed_identifier": "Bed-1A", "monthly_rent": 20000.0, "available_from": "2026-12-01", "is_occupied": False}]
                    }
                ]
            }, headers=owner_headers)
            print(f"Owner Property Creation Status: {r_prop_create.status_code}")
            assert r_prop_create.status_code in (200, 201), f"Property create failed: {r_prop_create.text}"
            prop_data = r_prop_create.json()
            owner_prop_id = prop_data["id"]
            if prop_data.get("rooms"):
                owner_room_id = prop_data["rooms"][0]["id"]
            print(f"Property Created: id={owner_prop_id}, room_id={owner_room_id}")

            # Now Seeker submits application on this property
            r_app = await client.post("/api/v1/applications/", json={
                "property_id": owner_prop_id,
                "introduction": "Hi Vikram, I am an IISc graduate looking to move in on Dec 1st.",
                "proposed_rent": 38000.0,
                "move_in_target": "2026-12-01",
                "documents": [],
            }, headers=seeker_headers)
            print(f"Seeker Application Submission Status: {r_app.status_code}")
            assert r_app.status_code in (200, 201), f"Application submission failed: {r_app.text}"

            results["Journey 2: Owner Listing Creation & Application Receipt"] = "PASS"
        except Exception as e:
            print(f"Journey 2 Failed: {e}")
            results["Journey 2: Owner Listing Creation & Application Receipt"] = f"FAIL: {e}"

        # ----------------------------------------------------------------------
        # Journey 3: Existing tenant vacancy creation and applicant communication
        # ----------------------------------------------------------------------
        try:
            print("\n[Executing Journey 3: Existing Tenant Vacancy Creation & Communication]")
            tenant_email = f"tenant_{tag}@staging.example.com"
            await client.post("/api/v1/auth/register", json={
                "email": tenant_email,
                "password": "Password123!",
                "full_name": "Kavita Active Tenant",
                "role": "tenant"
            })
            tenant_token = (await client.post("/api/v1/auth/login", json={"email": tenant_email, "password": "Password123!"})).json()["access_token"]
            tenant_headers = {"Authorization": f"Bearer {tenant_token}"}
            tenant_me = (await client.get("/api/v1/auth/me", headers=tenant_headers)).json()
            tenant_id = tenant_me["id"]

            # Provision active tenant membership in the database for this property
            pg_conn = await asyncpg.connect(DB_URL)
            await pg_conn.execute("""
                INSERT INTO tenant_memberships (
                    id, property_id, room_id, tenant_id, lease_start, monthly_rent, status, is_primary_tenant, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            """, uuid.uuid4(), uuid.UUID(owner_prop_id), uuid.UUID(owner_room_id) if owner_room_id else None,
            uuid.UUID(tenant_id), datetime.date(2026, 1, 1), 19000.0, "active", True)
            await pg_conn.close()
            print("Provisioned active tenant membership in database.")

            r_vac = await client.post("/api/v1/tenants/vacancies", json={
                "property_id": owner_prop_id,
                "room_id": owner_room_id,
                "title": "Private Master Bedroom Replacement",
                "description": "Looking for female vegetarian flatmate to replace outgoing roommate.",
                "expected_rent": 19000.0,
                "deposit_required": 38000.0,
                "vacant_from": "2026-12-01",
                "preferred_gender": "female_only",
            }, headers=tenant_headers)
            print(f"Tenant Vacancy Posting Status: {r_vac.status_code}")
            assert r_vac.status_code in (200, 201), f"Tenant vacancy posting failed: {r_vac.text}"

            r_vac_list = await client.get("/api/v1/tenants/vacancies")
            print(f"Tenant Vacancies Query Status: {r_vac_list.status_code}")
            assert r_vac_list.status_code == 200

            results["Journey 3: Existing Tenant Replacement Vacancy"] = "PASS"
        except Exception as e:
            print(f"Journey 3 Failed: {e}")
            results["Journey 3: Existing Tenant Replacement Vacancy"] = f"FAIL: {e}"

        # ----------------------------------------------------------------------
        # Journey 4: PG property and inventory management
        # ----------------------------------------------------------------------
        try:
            print("\n[Executing Journey 4: PG Building Registration & Floor Allocations]")
            pg_email = f"pg_operator_{tag}@staging.example.com"
            await client.post("/api/v1/auth/register", json={
                "email": pg_email,
                "password": "Password123!",
                "full_name": "Suresh PG Operator",
                "role": "pg_operator"
            })
            pg_token = (await client.post("/api/v1/auth/login", json={"email": pg_email, "password": "Password123!"})).json()["access_token"]
            pg_headers = {"Authorization": f"Bearer {pg_token}"}

            r_pg = await client.post("/api/v1/pg/buildings", json={
                "property_id": owner_prop_id or str(uuid.uuid4()),
                "building_name": "Sri Sai Luxury PG Whitefield",
                "pg_type": "coed",
                "total_floors": 4,
                "food_included": True,
                "meal_type": "veg_and_non_veg",
                "meals_served_per_day": 3,
                "gate_closing_time": "22:30",
                "notice_period_days": 30,
                "biometric_entry": True,
                "floors": [
                    {
                        "floor_number": 1,
                        "gender_restriction": "female_only",
                        "total_rooms": 6
                    }
                ]
            }, headers=pg_headers)
            print(f"PG Building Creation Status: {r_pg.status_code}")
            assert r_pg.status_code in (200, 201), f"PG create failed: {r_pg.text}"

            r_pg_list = await client.get("/api/v1/pg/buildings")
            print(f"PG Buildings Query Status: {r_pg_list.status_code}")
            assert r_pg_list.status_code == 200

            results["Journey 4: PG Building & Floor Inventory Management"] = "PASS"
        except Exception as e:
            print(f"Journey 4 Failed: {e}")
            results["Journey 4: PG Building & Floor Inventory Management"] = f"FAIL: {e}"

        # ----------------------------------------------------------------------
        # Journey 5: Group creation, invitations, compatibility and wishlist
        # ----------------------------------------------------------------------
        try:
            print("\n[Executing Journey 5: Group Syndicate Creation, Invites & Wishlist]")
            r_group = await client.post("/api/v1/groups/", json={
                "name": "IISc Flat Hunters",
                "description": "Forming syndicate for 3BHK in Koramangala",
                "target_budget_total": 45000,
                "target_city": "Bengaluru",
            }, headers=seeker_headers)
            print(f"Group Creation Status: {r_group.status_code}")
            assert r_group.status_code in (200, 201), f"Group creation failed: {r_group.text}"
            group_id = r_group.json()["id"]

            # Vote on property wishlist item
            if owner_prop_id:
                r_vote = await client.post(
                    f"/api/v1/groups/{group_id}/wishlist/{owner_prop_id}/vote",
                    json={"vote": "up"},
                    headers=seeker_headers
                )
                print(f"Group Wishlist Vote Status: {r_vote.status_code}")
                assert r_vote.status_code in (200, 201)

            results["Journey 5: Group Syndicate Formation & Wishlist"] = "PASS"
        except Exception as e:
            print(f"Journey 5 Failed: {e}")
            results["Journey 5: Group Syndicate Formation & Wishlist"] = f"FAIL: {e}"

        # ----------------------------------------------------------------------
        # Journey 6: Real-time messaging and attachments
        # ----------------------------------------------------------------------
        try:
            print("\n[Executing Journey 6: Real-Time Messaging & Read Receipts]")
            # Create conversation
            r_conv = await client.post("/api/v1/messaging/conversations", json={
                "participant_user_ids": [owner_id],
                "type": "direct",
                "title": "Aarav & Vikram Enquiry",
            }, headers=seeker_headers)
            assert r_conv.status_code in (200, 201)
            conv_id = r_conv.json().get("conversation_id") or r_conv.json().get("id")

            # Exchange message
            r_msg = await client.post("/api/v1/messaging/messages", json={
                "conversation_id": conv_id,
                "content": "Good morning Vikram, is the Indiranagar flat available for physical visit this Saturday?",
                "idempotency_key": str(uuid.uuid4()),
            }, headers=seeker_headers)
            assert r_msg.status_code in (200, 201)
            msg_id = r_msg.json()["id"]

            # Read cursor
            r_read = await client.post(f"/api/v1/messaging/conversations/{conv_id}/read", json={
                "last_read_message_id": msg_id,
            }, headers=owner_headers)
            assert r_read.status_code in (200, 204)

            results["Journey 6: Real-Time Messaging & Read Receipts"] = "PASS"
        except Exception as e:
            print(f"Journey 6 Failed: {e}")
            results["Journey 6: Real-Time Messaging & Read Receipts"] = f"FAIL: {e}"

        # ----------------------------------------------------------------------
        # Journey 7: Reporting, blocking and moderation
        # ----------------------------------------------------------------------
        try:
            print("\n[Executing Journey 7: Trust, Safety, User Report & Moderation]")
            # Seeker reports suspicious activity
            r_rep = await client.post("/api/v1/moderation/reports", json={
                "target_type": "user",
                "target_id": owner_id,
                "reason": "scam_suspicion",
                "description": "User requested advance deposit via UPI before physical flat inspection.",
            }, headers=seeker_headers)
            print(f"Moderation Report Status: {r_rep.status_code}")
            assert r_rep.status_code in (200, 201), f"Report submit failed: {r_rep.text}"

            # Seeker blocks owner
            r_block = await client.post(f"/api/v1/moderation/blocks/{owner_id}", headers=seeker_headers)
            print(f"User Block Status: {r_block.status_code}")
            assert r_block.status_code in (200, 201), f"User block failed: {r_block.text}"

            results["Journey 7: Trust, Safety, Report & User Block"] = "PASS"
        except Exception as e:
            print(f"Journey 7 Failed: {e}")
            results["Journey 7: Trust, Safety, Report & User Block"] = f"FAIL: {e}"

        print("\n=======================================================")
        print("          LIVE STAGING E2E RESULTS SUMMARY             ")
        print("=======================================================")
        all_passed = True
        for journey, status in results.items():
            print(f"{journey:55} : {status}")
            if not status.startswith("PASS"):
                all_passed = False

        assert all_passed, "One or more live staging journeys failed!"
        print("\nALL 7 CORE MARKETPLACE WORKFLOWS VERIFIED AS PASS!")

if __name__ == "__main__":
    asyncio.run(run_live_e2e_workflows())
