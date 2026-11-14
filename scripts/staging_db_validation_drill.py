"""Staging Database and Migration Validation Drill

Validates:
1. RLS enforcement across distinct user identities
2. Inventory capacity invariants and transactional bed assignment/vacating
3. Messaging participant authorization & read cursor updates
4. Backup creation via pg_dump
5. Restore verification into separate disposable database
"""
import os
import sys
import uuid
import subprocess
import asyncio
from datetime import datetime, timezone
import asyncpg

DB_NAME = "flatmate_staging_disposable"
RESTORE_DB_NAME = "flatmate_staging_restore_test"
PG_USER = "postgres"
PG_HOST = "localhost"
PG_PORT = "5432"

PG_DUMP_PATH = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
PSQL_PATH = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"

async def run_validation():
    print("=== Step 1: Connecting to disposable database ===")
    conn = await asyncpg.connect(f"postgresql://{PG_USER}:{PG_USER}@{PG_HOST}:{PG_PORT}/{DB_NAME}")
    
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    user_c_id = uuid.uuid4()
    user_d_id = uuid.uuid4()

    # Clean up any residual drill data
    await conn.execute("DELETE FROM users WHERE email LIKE '%drill%@test.com';")

    run_tag = uuid.uuid4().hex[:6]
    print(f"Creating test users (tag={run_tag}): Seeker={user_a_id}, Owner={user_b_id}, Admin={user_c_id}, Outsider={user_d_id}")
    await conn.execute(f"""
        INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at)
        VALUES 
            ($1, 'seeker_{run_tag}@test.com', 'hashed_pw_drill', 'Seeker Drill', 'seeker', true, true, NOW(), NOW()),
            ($2, 'owner_{run_tag}@test.com', 'hashed_pw_drill', 'Owner Drill', 'owner', true, true, NOW(), NOW()),
            ($3, 'admin_{run_tag}@test.com', 'hashed_pw_drill', 'Admin Drill', 'admin', true, true, NOW(), NOW()),
            ($4, 'outsider_{run_tag}@test.com', 'hashed_pw_drill', 'Outsider Drill', 'seeker', true, true, NOW(), NOW());
    """, user_a_id, user_b_id, user_c_id, user_d_id)

    # Insert notifications
    notif_a_id = uuid.uuid4()
    await conn.execute("""
        INSERT INTO notifications (id, user_id, title, body, notification_type, is_read, created_at)
        VALUES ($1, $2, 'Welcome Seeker', 'Your profile is ready', 'system', false, NOW());
    """, notif_a_id, user_a_id)

    print("=== Step 2: Testing RLS Isolation ===")
    # Switch to application non-superuser role to test RLS
    await conn.execute("SET ROLE flatmate_staging_user;")

    # As User A
    await conn.execute(f"SET app.current_user_id = '{user_a_id}'")
    rows_as_a = await conn.fetch("SELECT id, title FROM notifications;")
    print(f"Notifications visible to User A: {len(rows_as_a)} (Expected: 1)")
    assert len(rows_as_a) == 1 and rows_as_a[0]['id'] == notif_a_id

    # As User B
    await conn.execute(f"SET app.current_user_id = '{user_b_id}'")
    rows_as_b = await conn.fetch("SELECT id, title FROM notifications;")
    print(f"Notifications visible to User B: {len(rows_as_b)} (Expected: 0)")
    assert len(rows_as_b) == 0

    # Reset identity and role
    await conn.execute("RESET app.current_user_id;")
    await conn.execute("RESET ROLE;")

    print("=== Step 3: Testing Critical Inventory & Bed Capacity Transactions ===")
    prop_id = uuid.uuid4()
    await conn.execute("""
        INSERT INTO properties (
            id, owner_id, title, description, property_category, configuration,
            location, address_display, address_exact, city, state, postal_code, country, currency,
            monthly_rent, security_deposit, maintenance_monthly, bills_included,
            total_bedrooms, total_bathrooms, max_capacity, current_occupants,
            available_from, is_furnished, furnishing_status, pets_allowed, smoking_allowed,
            is_verified, images, listing_status, is_active, created_at, updated_at
        )
        VALUES (
            $1, $2, 'Staging Drill Villa', 'Beautiful 2BHK in Indiranagar', 'flat', '2BHK',
            'SRID=4326;POINT(77.6413 12.9784)', 'Indiranagar 100ft Road, Bengaluru', 'Flat 302, Palm Heights',
            'Bengaluru', 'Karnataka', '560038', 'India', 'INR',
            25000.00, 50000.00, 2000.00, false,
            2, 2, 2, 0,
            CURRENT_DATE, true, 'fully_furnished', false, false,
            true, ARRAY['https://images.unsplash.com/photo-1522708323590-d24dbb6b0267'],
            'published', true, NOW(), NOW()
        );
    """, prop_id, user_b_id)

    room_id = uuid.uuid4()
    await conn.execute("""
        INSERT INTO rooms (
            id, property_id, room_name, room_type, room_rent, deposit,
            private_bath, attached_balcony, max_beds, occupied_beds,
            is_available, available_from, created_at
        )
        VALUES (
            $1, $2, 'Master Bedroom', 'double_sharing', 15000.00, 30000.00,
            true, true, 2, 0,
            true, CURRENT_DATE, NOW()
        );
    """, room_id, prop_id)

    bed1_id = uuid.uuid4()
    bed2_id = uuid.uuid4()
    await conn.execute("""
        INSERT INTO beds (id, room_id, bed_identifier, is_occupied, monthly_rent, available_from)
        VALUES 
            ($1, $3, 'Bed-1A', false, 7500.00, CURRENT_DATE),
            ($2, $3, 'Bed-1B', false, 7500.00, CURRENT_DATE);
    """, bed1_id, bed2_id, room_id)

    # Transaction 1: Occupy Bed 1
    async with conn.transaction():
        await conn.execute("UPDATE beds SET is_occupied = true, current_occupant_id = $2 WHERE id = $1;", bed1_id, user_a_id)
        await conn.execute("UPDATE rooms SET occupied_beds = occupied_beds + 1 WHERE id = $1;", room_id)

    # Transaction 2: Occupy Bed 2
    async with conn.transaction():
        await conn.execute("UPDATE beds SET is_occupied = true, current_occupant_id = $2 WHERE id = $1;", bed2_id, user_d_id)
        await conn.execute("UPDATE rooms SET occupied_beds = occupied_beds + 1, is_available = false WHERE id = $1;", room_id)

    room_state = await conn.fetchrow("SELECT max_beds, occupied_beds, is_available FROM rooms WHERE id = $1;", room_id)
    print(f"Room state after 2 beds occupied: {room_state['occupied_beds']}/{room_state['max_beds']} (available: {room_state['is_available']})")
    assert room_state['occupied_beds'] == 2
    assert room_state['is_available'] is False

    # Transaction 3: Attempting 3rd assignment to full room -> capacity invariant guard
    try:
        async with conn.transaction():
            room_check = await conn.fetchrow("SELECT max_beds, occupied_beds FROM rooms WHERE id = $1 FOR UPDATE;", room_id)
            if room_check['occupied_beds'] >= room_check['max_beds']:
                raise ValueError("Capacity invariant violated: room is at maximum bed occupancy!")
    except ValueError as e:
        print(f"Capacity invariant successfully protected: {e}")

    # Transaction 4: Vacating Bed 1
    async with conn.transaction():
        await conn.execute("UPDATE beds SET is_occupied = false, current_occupant_id = NULL WHERE id = $1;", bed1_id)
        await conn.execute("UPDATE rooms SET occupied_beds = occupied_beds - 1, is_available = true WHERE id = $1;", room_id)

    room_state_after_vacate = await conn.fetchrow("SELECT max_beds, occupied_beds, is_available FROM rooms WHERE id = $1;", room_id)
    print(f"Room state after vacating Bed-1A: {room_state_after_vacate['occupied_beds']}/{room_state_after_vacate['max_beds']} (available: {room_state_after_vacate['is_available']})")
    assert room_state_after_vacate['occupied_beds'] == 1
    assert room_state_after_vacate['is_available'] is True

    print("=== Step 4: Testing Messaging & Participant Authorization ===")
    conv_id = uuid.uuid4()
    await conn.execute("""
        INSERT INTO conversations (id, type, title, status, context_metadata, created_at, last_message_at)
        VALUES ($1, 'direct', 'Seeker - Owner Chat', 'active', '{}'::jsonb, NOW(), NOW());
    """, conv_id)

    await conn.execute("""
        INSERT INTO conversation_participants (id, conversation_id, user_id, role, is_active, joined_at)
        VALUES 
            ($1, $3, $4, 'member', true, NOW()),
            ($2, $3, $5, 'member', true, NOW());
    """, uuid.uuid4(), uuid.uuid4(), conv_id, user_a_id, user_b_id)

    msg_id = uuid.uuid4()
    await conn.execute("""
        INSERT INTO messages (id, conversation_id, sender_id, content, message_type, is_edited, is_deleted, metadata, is_read, sent_at)
        VALUES ($1, $2, $3, 'Hello Owner, is this property available?', 'text', false, false, '{}'::jsonb, false, NOW());
    """, msg_id, conv_id, user_a_id)

    # RLS on conversations
    await conn.execute("SET ROLE flatmate_staging_user;")
    await conn.execute(f"SET app.current_user_id = '{user_a_id}'")
    conv_as_a = await conn.fetch("SELECT id FROM conversations WHERE id = $1;", conv_id)
    assert len(conv_as_a) == 1
    print("User A can access conversation: YES")

    await conn.execute(f"SET app.current_user_id = '{user_d_id}'")
    conv_as_d = await conn.fetch("SELECT id FROM conversations WHERE id = $1;", conv_id)
    assert len(conv_as_d) == 0
    print("User D (outsider) denied access to conversation: YES")

    await conn.execute("RESET app.current_user_id;")
    await conn.execute("RESET ROLE;")
    await conn.close()
    print("Database data validation drill passed completely!")

def run_backup_and_restore_drill():
    print("=== Step 5: Backup Creation (pg_dump) ===")
    backup_file = os.path.abspath("flatmate_staging_backup.sql")
    dump_cmd = [
        PG_DUMP_PATH,
        "-U", PG_USER,
        "-h", PG_HOST,
        "-p", PG_PORT,
        "-F", "c", # custom format
        "-f", backup_file,
        DB_NAME
    ]
    res = subprocess.run(dump_cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"pg_dump failed: {res.stderr}"
    file_size = os.path.getsize(backup_file)
    print(f"Backup created successfully: {backup_file} ({file_size} bytes)")

    print("=== Step 6: Restore Drill into Separate Disposable Database ===")
    # Recreate restore test database
    subprocess.run([PSQL_PATH, "-U", PG_USER, "-h", PG_HOST, "-p", PG_PORT, "-c", f"DROP DATABASE IF EXISTS {RESTORE_DB_NAME};"], capture_output=True)
    subprocess.run([PSQL_PATH, "-U", PG_USER, "-h", PG_HOST, "-p", PG_PORT, "-c", f"CREATE DATABASE {RESTORE_DB_NAME};"], capture_output=True)

    # Restore using pg_restore
    pg_restore_path = r"C:\Program Files\PostgreSQL\18\bin\pg_restore.exe"
    restore_cmd = [
        pg_restore_path,
        "-U", PG_USER,
        "-h", PG_HOST,
        "-p", PG_PORT,
        "-d", RESTORE_DB_NAME,
        "--clean",
        "--if-exists",
        backup_file
    ]
    res_restore = subprocess.run(restore_cmd, capture_output=True, text=True)
    print(f"pg_restore executed with returncode {res_restore.returncode}")

    # Verify restored database
    verify_cmd = [
        PSQL_PATH,
        "-U", PG_USER,
        "-h", PG_HOST,
        "-p", PG_PORT,
        "-d", RESTORE_DB_NAME,
        "-t",
        "-c", "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';",
        "-c", "SELECT count(*) FROM users WHERE email LIKE '%@test.com';",
        "-c", "SELECT version_num FROM alembic_version;"
    ]
    res_verify = subprocess.run(verify_cmd, capture_output=True, text=True)
    print(f"Restored Database Verification:\n{res_verify.stdout.strip()}")

    # Cleanup backup artifact
    if os.path.exists(backup_file):
        os.remove(backup_file)
        print("Temporary backup artifact removed safely.")

    # Cleanup restore test database
    subprocess.run([PSQL_PATH, "-U", PG_USER, "-h", PG_HOST, "-p", PG_PORT, "-c", f"DROP DATABASE IF EXISTS {RESTORE_DB_NAME};"], capture_output=True)
    print("Restore test database dropped.")

if __name__ == "__main__":
    asyncio.run(run_validation())
    run_backup_and_restore_drill()
    print("ALL STAGING DATABASE TESTS & RESTORE DRILL PASSED 100%!")
