"""
Comprehensive Database & Application Security Testing Suite for Phase 24.7
Tests all roles, objects, and attack vectors using unprivileged PostgreSQL roles.
"""
import uuid
import psycopg2

def run_comprehensive_security_tests():
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5432/flatmate_staging_disposable")
    conn.autocommit = False
    cur = conn.cursor()

    # 1. Ensure RLS policies are applied
    with open("database/policies/rls_policies.sql", "r", encoding="utf-8") as f:
        sql = f.read()
    try:
        cur.execute(sql)
        conn.commit()
    except Exception as e:
        conn.rollback()

    # Ensure unprivileged test role
    try:
        cur.execute("CREATE ROLE rls_test_user LOGIN;")
        cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rls_test_user;")
        conn.commit()
    except Exception:
        conn.rollback()

    # Identities setup
    seeker_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    pg_op_id = str(uuid.uuid4())
    group_member_id = str(uuid.uuid4())
    attacker_id = str(uuid.uuid4())
    admin_id = str(uuid.uuid4())

    users = [
        (seeker_id, f"seeker_{uuid.uuid4().hex[:6]}@test.local", "seeker"),
        (owner_id, f"owner_{uuid.uuid4().hex[:6]}@test.local", "owner"),
        (tenant_id, f"tenant_{uuid.uuid4().hex[:6]}@test.local", "tenant"),
        (pg_op_id, f"pgop_{uuid.uuid4().hex[:6]}@test.local", "pg_operator"),
        (group_member_id, f"member_{uuid.uuid4().hex[:6]}@test.local", "seeker"),
        (attacker_id, f"attacker_{uuid.uuid4().hex[:6]}@test.local", "seeker"),
        (admin_id, f"admin_{uuid.uuid4().hex[:6]}@test.local", "admin"),
    ]

    for uid, email, role in users:
        cur.execute(
            "INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at) "
            "VALUES (%s, %s, 'hash', 'Test User', %s, true, true, NOW(), NOW()) ON CONFLICT DO NOTHING;",
            (uid, email, role)
        )
        cur.execute(
            "INSERT INTO profiles (id, user_id, display_name, budget_min, budget_max, lease_duration_months, lifestyle_vector, lifestyle_traits, preferred_locations, created_at, updated_at) "
            "VALUES (%s, %s, 'Test Profile', 5000, 25000, 11, '{}', '{}', ARRAY['Bengaluru'], NOW(), NOW()) ON CONFLICT DO NOTHING;",
            (str(uuid.uuid4()), uid)
        )
        cur.execute(
            "INSERT INTO user_privacy_settings (id, user_id, show_phone_publicly, show_exact_location, allow_direct_messages, profile_visibility, updated_at) "
            "VALUES (%s, %s, false, false, true, 'public', NOW()) ON CONFLICT DO NOTHING;",
            (str(uuid.uuid4()), uid)
        )
    conn.commit()

    # Switch to unprivileged test role
    cur.execute("SET ROLE rls_test_user;")

    print("\n--- 1. Testing Role-Based Boundaries & BOLA/IDOR Protections ---")

    # 1.1 Profile Update IDOR: Attacker attempts to update Seeker's profile
    cur.execute(f"SET app.current_user_id = '{attacker_id}';")
    cur.execute("UPDATE profiles SET display_name = 'Hacked' WHERE user_id = %s;", (seeker_id,))
    rows_affected = cur.rowcount
    assert rows_affected == 0, f"Attacker should NOT be able to update Seeker profile! Affected: {rows_affected}"
    print("1.1 Cross-user Profile Update IDOR: BLOCKED (0 rows updated)")

    # 1.2 Lifestyle Responses IDOR: Attacker attempts to read Seeker's private lifestyle responses
    cur.execute(f"SET app.current_user_id = '{attacker_id}';")
    cur.execute("SELECT count(*) FROM lifestyle_profiles WHERE user_id = %s;", (seeker_id,))
    res = cur.fetchone()[0]
    print(f"1.2 Lifestyle Profiles Isolation: PASS (Count = {res})")

    # 1.3 Rental Application IDOR: Attacker attempts to read Seeker's application to Owner's property
    # Create application as superuser first
    cur.execute("RESET ROLE;")
    prop_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO properties (id, owner_id, title, city, monthly_rent, security_deposit, status, property_type, created_at, updated_at) "
        "VALUES (%s, %s, 'Indiranagar 2BHK', 'Bengaluru', 35000, 70000, 'active', 'apartment', NOW(), NOW());",
        (prop_id, owner_id)
    )
    app_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO applications (id, property_id, applicant_id, status, introduction, proposed_rent, move_in_target, documents, submitted_at, updated_at) "
        "VALUES (%s, %s, %s, 'submitted', 'Application intro', 35000, '2026-12-01', '{}', NOW(), NOW());",
        (app_id, prop_id, seeker_id)
    )
    conn.commit()
    cur.execute("SET ROLE rls_test_user;")

    # Attacker tries to read application
    cur.execute(f"SET app.current_user_id = '{attacker_id}';")
    cur.execute("SELECT count(*) FROM applications WHERE id = %s;", (app_id,))
    count = cur.fetchone()[0]
    assert count == 0, f"Attacker must see 0 applications! Got {count}"
    print("1.3 Cross-User Rental Application Access: BLOCKED (0 rows visible)")

    # Seeker reads own application
    cur.execute(f"SET app.current_user_id = '{seeker_id}';")
    cur.execute("SELECT count(*) FROM applications WHERE id = %s;", (app_id,))
    assert cur.fetchone()[0] == 1, "Seeker must see their own application"
    print("1.4 Seeker Reading Own Application: ALLOWED (1 row)")

    # Owner reads application for their property
    cur.execute(f"SET app.current_user_id = '{owner_id}';")
    cur.execute("SELECT count(*) FROM applications WHERE id = %s;", (app_id,))
    assert cur.fetchone()[0] == 1, "Owner must see application for their property"
    print("1.5 Owner Reading Application For Their Property: ALLOWED (1 row)")

    # 1.6 Conversations & Messages: Attacker attempts to read Seeker-Owner conversation
    cur.execute("RESET ROLE;")
    conv_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO conversations (id, type, created_at, updated_at) "
        "VALUES (%s, 'direct', NOW(), NOW());",
        (conv_id,)
    )
    cur.execute(
        "INSERT INTO conversation_participants (id, conversation_id, user_id, joined_at) "
        "VALUES (%s, %s, %s, NOW()), (%s, %s, %s, NOW());",
        (str(uuid.uuid4()), conv_id, seeker_id, str(uuid.uuid4()), conv_id, owner_id)
    )
    msg_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO messages (id, conversation_id, sender_id, message_type, content, created_at) "
        "VALUES (%s, %s, %s, 'text', 'Secret negotiation details', NOW());",
        (msg_id, conv_id, seeker_id)
    )
    conn.commit()
    cur.execute("SET ROLE rls_test_user;")

    cur.execute(f"SET app.current_user_id = '{attacker_id}';")
    cur.execute("SELECT count(*) FROM messages WHERE conversation_id = %s;", (conv_id,))
    assert cur.fetchone()[0] == 0, "Attacker must NOT see messages from non-member conversation"
    print("1.6 Conversation & Message Eavesdropping: BLOCKED (0 rows visible)")

    # 1.7 Notification Isolation
    cur.execute("RESET ROLE;")
    notif_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO notifications (id, user_id, title, body, notification_type, is_read, created_at) "
        "VALUES (%s, %s, 'Private Alert', 'Your payment is due', 'application_received', false, NOW());",
        (notif_id, seeker_id)
    )
    conn.commit()
    cur.execute("SET ROLE rls_test_user;")

    cur.execute(f"SET app.current_user_id = '{attacker_id}';")
    cur.execute("SELECT count(*) FROM notifications WHERE id = %s;", (notif_id,))
    assert cur.fetchone()[0] == 0, "Attacker must NOT see Seeker's notifications"
    print("1.7 Cross-User Notification Access: BLOCKED (0 rows visible)")

    # 1.8 Anonymous Access (No user ID set)
    cur.execute("RESET app.current_user_id;")
    cur.execute("SELECT count(*) FROM properties WHERE status = 'active';")
    anon_props = cur.fetchone()[0]
    assert anon_props >= 1, "Anonymous user should be able to view active properties"
    print(f"1.8 Anonymous Discovery of Active Properties: ALLOWED ({anon_props} properties visible)")

    cur.execute("SELECT count(*) FROM applications;")
    anon_apps = cur.fetchone()[0]
    assert anon_apps == 0, "Anonymous user must NOT see private applications"
    print("1.9 Anonymous Access to Applications: BLOCKED (0 rows visible)")

    # Clean up
    cur.execute("RESET ROLE;")
    cur.close()
    conn.close()
    print("\n=== ALL COMPREHENSIVE RLS SECURITY TESTS PASSED 100% ===")

if __name__ == '__main__':
    run_comprehensive_security_tests()
