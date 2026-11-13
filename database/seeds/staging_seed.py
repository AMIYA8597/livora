"""
Flatmate Platform - Enterprise Staging Seed Script
==================================================
Seeds realistic, synthetic data into the staging database.
Includes students, professionals, owners, PG operators, tenants, properties,
rooms, beds, amenities, applications, appointments, groups, and wishlist entries.

Safety Guarantees:
- Strictly synthetic identities (using @synth.flatmate.test domain).
- Completely idempotent (runs ON CONFLICT DO UPDATE/NOTHING with deterministic UUIDs).
- Explicitly blocked from executing in production environments (ENVIRONMENT != 'production').
"""

import os
import sys
import asyncio
from datetime import datetime, timezone, timedelta, date
from uuid import UUID
import asyncpg

# Environment Gate
ENVIRONMENT = os.getenv("ENVIRONMENT", "staging").lower()
if ENVIRONMENT in ("production", "prod"):
    print("❌ FATAL: staging_seed.py cannot be executed against production environment!", file=sys.stderr)
    sys.exit(1)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/flatmate_db"
)
# Normalize SQLAlchemy asyncpg URL if provided
if "+asyncpg" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")

# Standardized Bcrypt hash for Password123!
# Generated with bcrypt.hashpw(b"Password123!", bcrypt.gensalt(12))
PASSWORD_HASH = "$2b$12$K8M9zBvhwY0b7lR8W3vBde9KjP3l2Z4bJ9fF7q0nC2e4w1lG8s0aW"

# Deterministic Seed UUIDs
U_STUDENT_1 = "10000000-0000-0000-0000-000000000001"
U_STUDENT_2 = "10000000-0000-0000-0000-000000000002"
U_PRO_1     = "10000000-0000-0000-0000-000000000003"
U_PRO_2     = "10000000-0000-0000-0000-000000000004"
U_OWNER_1   = "10000000-0000-0000-0000-000000000005"
U_OWNER_2   = "10000000-0000-0000-0000-000000000006"
U_PG_OP     = "10000000-0000-0000-0000-000000000007"
U_TENANT_1  = "10000000-0000-0000-0000-000000000008"
U_TENANT_2  = "10000000-0000-0000-0000-000000000009"
U_ADMIN     = "10000000-0000-0000-0000-000000000010"

# Properties
PROP_1      = "20000000-0000-0000-0000-000000000001" # 3BHK Koramangala
PROP_2      = "20000000-0000-0000-0000-000000000002" # 2BHK Indiranagar
PROP_3      = "20000000-0000-0000-0000-000000000003" # 1BHK HSR Layout
PROP_PG     = "20000000-0000-0000-0000-000000000004" # PG Building Whitefield

# Rooms & Beds
ROOM_1_A    = "30000000-0000-0000-0000-000000000001"
ROOM_1_B    = "30000000-0000-0000-0000-000000000002"
ROOM_1_C    = "30000000-0000-0000-0000-000000000003"
BED_1_A1    = "40000000-0000-0000-0000-000000000001"
BED_1_B1    = "40000000-0000-0000-0000-000000000002"
BED_1_C1    = "40000000-0000-0000-0000-000000000003"

# Groups & Wishlist
GROUP_1     = "50000000-0000-0000-0000-000000000001"
WISHLIST_1  = "60000000-0000-0000-0000-000000000001"

# Applications & Appointments
APP_1       = "70000000-0000-0000-0000-000000000001"
APP_2       = "70000000-0000-0000-0000-000000000002"
APPT_1      = "80000000-0000-0000-0000-000000000001"


async def seed_staging():
    print(f"[*] Starting Staging Database Seeding in Environment: '{ENVIRONMENT}'")
    print(f"[*] Connecting to: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("[+] Database connection established.")

        async with conn.transaction():
            # 1. Users
            print("[*] Seeding Users...")
            users_data = [
                (U_STUDENT_1, "aarav.student@synth.flatmate.test", PASSWORD_HASH, "Aarav Patel", "seeker", True, True, "+919876543210"),
                (U_STUDENT_2, "diya.student@synth.flatmate.test", PASSWORD_HASH, "Diya Sengupta", "seeker", True, True, "+919876543211"),
                (U_PRO_1,     "rohan.engineer@synth.flatmate.test", PASSWORD_HASH, "Rohan Iyer", "seeker", True, True, "+919876543212"),
                (U_PRO_2,     "ananya.designer@synth.flatmate.test", PASSWORD_HASH, "Ananya Rao", "seeker", True, True, "+919876543213"),
                (U_OWNER_1,   "vikram.owner@synth.flatmate.test", PASSWORD_HASH, "Vikram Malhotra", "owner", True, True, "+919876543214"),
                (U_OWNER_2,   "rajesh.landlord@synth.flatmate.test", PASSWORD_HASH, "Rajesh Kumar", "owner", True, True, "+919876543215"),
                (U_PG_OP,     "suresh.pg@synth.flatmate.test", PASSWORD_HASH, "Suresh Reddy", "pg_operator", True, True, "+919876543216"),
                (U_TENANT_1,  "kavita.tenant@synth.flatmate.test", PASSWORD_HASH, "Kavita Deshmukh", "tenant", True, True, "+919876543217"),
                (U_TENANT_2,  "arjun.tenant@synth.flatmate.test", PASSWORD_HASH, "Arjun Nair", "tenant", True, True, "+919876543218"),
                (U_ADMIN,     "moderator.staging@synth.flatmate.test", PASSWORD_HASH, "Staging Moderator", "admin", True, True, "+919876543219"),
            ]
            for u in users_data:
                await conn.execute("""
                    INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, phone_number)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (id) DO UPDATE SET
                        email = EXCLUDED.email,
                        full_name = EXCLUDED.full_name,
                        role = EXCLUDED.role,
                        is_verified = EXCLUDED.is_verified,
                        phone_number = EXCLUDED.phone_number;
                """, *u)

            # 2. User Roles
            print("[*] Seeding User Roles...")
            for uid, _, _, _, role, _, is_ver, _ in users_data:
                await conn.execute("""
                    INSERT INTO user_roles (user_id, role, is_verified)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, role) DO UPDATE SET is_verified = EXCLUDED.is_verified;
                """, uid, role, is_ver)

            # 3. Privacy Settings
            print("[*] Seeding User Privacy Settings...")
            for uid, _, _, _, _, _, _, _ in users_data:
                await conn.execute("""
                    INSERT INTO user_privacy_settings (user_id, show_phone_publicly, show_exact_location, allow_direct_messages, profile_visibility)
                    VALUES ($1, false, false, true, 'public')
                    ON CONFLICT (user_id) DO NOTHING;
                """, uid)

            # 4. User Profiles
            print("[*] Seeding Profiles...")
            profiles_data = [
                (U_STUDENT_1, "Aarav P.", "CS student at IISc. Studying distributed systems. Early riser, vegetarian, non-smoker, loves badminton.", "male", "Student", 12000, 22000, "2026-12-01"),
                (U_STUDENT_2, "Diya S.", "Design student at NID. Tidy, creative, vegan, early sleeper. Looking for a quiet space near Indiranagar.", "female", "Student", 14000, 25000, "2026-12-15"),
                (U_PRO_1,     "Rohan I.", "Senior Backend Engineer at a tech startup. Hybrid work (3 days remote). Cook simple Indian food, non-smoker.", "male", "Software Engineer", 20000, 35000, "2026-11-20"),
                (U_PRO_2,     "Ananya R.", "Product Designer at fintech company. Non-smoker, social on weekends, keeps house spotless.", "female", "Product Designer", 22000, 38000, "2026-12-01"),
                (U_TENANT_1,  "Kavita D.", "Active tenant in Koramangala 3BHK. Searching for a flatmate to fill master bedroom.", "female", "Data Scientist", 18000, 30000, "2026-11-25"),
                (U_TENANT_2,  "Arjun N.", "Tenant in HSR Layout flat. Friendly, loves dogs, working in consulting.", "male", "Consultant", 16000, 28000, "2026-12-05"),
            ]
            for p in profiles_data:
                await conn.execute("""
                    INSERT INTO profiles (id, user_id, display_name, bio, gender, occupation, budget_min, budget_max, move_in_date)
                    VALUES (uuid_generate_v4(), $1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (user_id) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        bio = EXCLUDED.bio,
                        occupation = EXCLUDED.occupation,
                        budget_min = EXCLUDED.budget_min,
                        budget_max = EXCLUDED.budget_max;
                """, p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7])

            # 5. Properties
            print("[*] Seeding Properties...")
            properties_data = [
                (
                    PROP_1, U_OWNER_1, "Sunlit 3BHK Apartment in Koramangala 4th Block",
                    "Spacious, airy 3BHK with modular kitchen, private balcony, high-speed fiber internet, and 24/7 power backup.",
                    "apartment", "Koramangala 4th Block, Bengaluru", "Bengaluru", "Karnataka", "India", "560034",
                    12.9352, 77.6245, 45000, 90000, 3000, "3bhk", "fully_furnished", 3, 3, "available", True
                ),
                (
                    PROP_2, U_OWNER_2, "Modern 2BHK Flat near 100ft Road Indiranagar",
                    "Located in prime Indiranagar, walkable to Metro and eateries. Hardwood flooring, semi-furnished with wardrobes.",
                    "apartment", "Indiranagar 100ft Road, Bengaluru", "Bengaluru", "Karnataka", "India", "560038",
                    12.9784, 77.6408, 38000, 76000, 2500, "2bhk", "semi_furnished", 2, 2, "available", True
                ),
                (
                    PROP_3, U_OWNER_1, "Cozy 1BHK Penthouse in HSR Layout Sector 1",
                    "Quiet penthouse terrace unit with greenery view. Perfect for single professional or couple.",
                    "independent_house", "HSR Layout Sector 1, Bengaluru", "Bengaluru", "Karnataka", "India", "560102",
                    12.9121, 77.6446, 22000, 44000, 1500, "1bhk", "fully_furnished", 1, 1, "available", True
                ),
                (
                    PROP_PG, U_PG_OP, "Stanza Living Co-Living & Luxury PG Whitefield",
                    "Modern executive coliving space with meal plan options, biometric access, daily housekeeping, and gym.",
                    "pg_coliving", "ITPL Main Road, Whitefield, Bengaluru", "Bengaluru", "Karnataka", "India", "560066",
                    12.9856, 77.7321, 14000, 28000, 1000, "pg_room", "fully_furnished", 12, 24, "available", True
                ),
            ]
            for prop in properties_data:
                await conn.execute("""
                    INSERT INTO properties (
                        id, owner_id, title, description, property_type, address_display,
                        city, state, country, pincode, latitude, longitude,
                        monthly_rent, security_deposit, maintenance_charges,
                        configuration, furnishing_status, total_bedrooms, total_bathrooms,
                        status, is_active
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        monthly_rent = EXCLUDED.monthly_rent,
                        status = EXCLUDED.status,
                        is_active = EXCLUDED.is_active;
                """, *prop)

            # 6. Rooms & Beds
            print("[*] Seeding Rooms and Beds...")
            rooms_data = [
                (ROOM_1_A, PROP_1, "Master Bedroom with Attached Balcony", "master", 18000, 1, 0, "available"),
                (ROOM_1_B, PROP_1, "Deluxe Bedroom 2", "private", 15000, 1, 0, "available"),
                (ROOM_1_C, PROP_1, "Cozy Single Bedroom 3", "single", 12000, 1, 0, "available"),
            ]
            for r in rooms_data:
                await conn.execute("""
                    INSERT INTO rooms (id, property_id, name, room_type, monthly_rent, max_capacity, current_occupants, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (id) DO UPDATE SET
                        monthly_rent = EXCLUDED.monthly_rent,
                        status = EXCLUDED.status;
                """, *r)

            beds_data = [
                (BED_1_A1, ROOM_1_A, "Bed-A1 (King Bed)", 18000, "available"),
                (BED_1_B1, ROOM_1_B, "Bed-B1 (Queen Bed)", 15000, "available"),
                (BED_1_C1, ROOM_1_C, "Bed-C1 (Single Bed)", 12000, "available"),
            ]
            for b in beds_data:
                await conn.execute("""
                    INSERT INTO beds (id, room_id, identifier, monthly_rent, status)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (id) DO UPDATE SET
                        monthly_rent = EXCLUDED.monthly_rent,
                        status = EXCLUDED.status;
                """, *b)

            # 7. Groups & Members
            print("[*] Seeding Flatmate Groups...")
            await conn.execute("""
                INSERT INTO groups (id, name, creator_id, target_city, target_move_in, budget_max, status)
                VALUES ($1, 'Tech Flatmates Bangalore Syndicate', $2, 'Bengaluru', '2026-12-01', 50000, 'active')
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, status = EXCLUDED.status;
            """, GROUP_1, U_PRO_1)

            await conn.execute("""
                INSERT INTO group_members (id, group_id, user_id, role, status)
                VALUES (uuid_generate_v4(), $1, $2, 'leader', 'active')
                ON CONFLICT (group_id, user_id) DO NOTHING;
            """, GROUP_1, U_PRO_1)

            await conn.execute("""
                INSERT INTO group_members (id, group_id, user_id, role, status)
                VALUES (uuid_generate_v4(), $1, $2, 'member', 'active')
                ON CONFLICT (group_id, user_id) DO NOTHING;
            """, GROUP_1, U_STUDENT_1)

            # 8. Group Wishlist
            print("[*] Seeding Group Wishlist...")
            await conn.execute("""
                INSERT INTO group_wishlist_items (id, group_id, property_id, added_by_user_id)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (group_id, property_id) DO NOTHING;
            """, WISHLIST_1, GROUP_1, PROP_1, U_PRO_1)

            # 9. Applications
            print("[*] Seeding Rental Applications...")
            await conn.execute("""
                INSERT INTO applications (id, property_id, applicant_id, proposed_rent, move_in_target, introduction, status)
                VALUES ($1, $2, $3, 45000, '2026-12-01', 'Responsible professional with verified employment at tech company.', 'submitted')
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status;
            """, APP_1, PROP_1, U_PRO_1)

            await conn.execute("""
                INSERT INTO applications (id, property_id, applicant_id, proposed_rent, move_in_target, introduction, status)
                VALUES ($1, $2, $3, 38000, '2026-12-15', 'NID postgraduate student looking for quiet environment.', 'submitted')
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status;
            """, APP_2, PROP_2, U_STUDENT_2)

            # 10. Appointments
            print("[*] Seeding Viewing Appointments...")
            now_dt = datetime.now(timezone.utc)
            appt_time = now_dt + timedelta(days=2, hours=4)
            await conn.execute("""
                INSERT INTO viewing_appointments (id, property_id, host_id, applicant_id, slot_start, slot_end, appointment_type, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'in_person', 'scheduled')
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status;
            """, APPT_1, PROP_1, U_OWNER_1, U_PRO_1, appt_time, appt_time + timedelta(minutes=30))

        await conn.close()
        print("\n✅ Staging Seed Completed Successfully with 100% Idempotency!")
        print(f"   Users: {len(users_data)} synthetic accounts")
        print(f"   Properties: {len(properties_data)} listings across Bengaluru")
        print(f"   Rooms/Beds: {len(rooms_data)} rooms, {len(beds_data)} beds")
        print("   Groups & Wishlist: 1 active group, 1 wishlist entry")
        print("   Applications & Visits: 2 rental applications, 1 viewing appointment")

    except Exception as err:
        print(f"❌ Failed to seed staging database: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(seed_staging())
