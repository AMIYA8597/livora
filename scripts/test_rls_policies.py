"""
Empirical RLS and Authorization Verification Suite
Tests Postgres RLS policies directly using non-superuser contexts.
"""
import uuid
import psycopg2

def run_rls_tests():
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5432/flatmate_staging_disposable")
    conn.autocommit = False
    cur = conn.cursor()

    print("--- 1. Applying RLS Policies from database/policies/rls_policies.sql ---")
    with open("database/policies/rls_policies.sql", "r", encoding="utf-8") as f:
        sql = f.read()
    try:
        cur.execute(sql)
        conn.commit()
        print("RLS Policies applied successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Policy application note (may already exist): {e}")

    # Use existing seeded users
    cur.execute("SELECT id, role FROM users LIMIT 10;")
    users = cur.fetchall()
    print(f"Found {len(users)} users in database.")

    # Find a seeker, an owner, and an admin
    cur.execute("SELECT id FROM users WHERE role = 'seeker' LIMIT 1;")
    user_a = str(cur.fetchone()[0])
    cur.execute("SELECT id FROM users WHERE role = 'owner' LIMIT 1;")
    user_b = str(cur.fetchone()[0])
    cur.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1;")
    admin_row = cur.fetchone()
    admin_u = str(admin_row[0]) if admin_row else str(uuid.uuid4())

    # Create a fresh outsider seeker
    outsider_tag = uuid.uuid4().hex[:6]
    outsider_u = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at) "
        "VALUES (%s, %s, 'hash', 'Outsider Seeker', 'seeker', true, true, NOW(), NOW());",
        (outsider_u, f"outsider_{outsider_tag}@test.local")
    )
    conn.commit()

    # Find a property owned by user_b
    cur.execute("SELECT id FROM properties WHERE owner_id = %s LIMIT 1;", (user_b,))
    prop_row = cur.fetchone()
    if prop_row:
        prop_id = str(prop_row[0])
    else:
        cur.execute("SELECT id, owner_id FROM properties LIMIT 1;")
        p_row = cur.fetchone()
        prop_id = str(p_row[0])
        user_b = str(p_row[1])

    print(f"Test Identities: Seeker={user_a[:8]}..., Owner={user_b[:8]}..., Outsider={outsider_u[:8]}...")
    print(f"Test Property: {prop_id[:8]}...")

    # Create test application from user_a to prop_id
    app_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO applications (id, property_id, applicant_id, status, introduction, proposed_rent, move_in_target, documents, submitted_at, updated_at) "
        "VALUES (%s, %s, %s, 'submitted', 'Hi, I am interested in this flat.', 30000.00, '2026-12-01', '{}', NOW(), NOW());",
        (app_id, prop_id, user_a)
    )
    conn.commit()

    # Create unprivileged role to test RLS
    try:
        cur.execute("CREATE ROLE rls_test_user LOGIN;")
        conn.commit()
    except Exception:
        conn.rollback()

    try:
        cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rls_test_user;")
        conn.commit()
    except Exception:
        conn.rollback()

    cur.execute("SET ROLE rls_test_user;")

    print("\n--- 3. Testing RLS on Applications ---")
    # 3.1 Applicant User A queries applications
    cur.execute(f"SET app.current_user_id = '{user_a}';")
    cur.execute("SELECT count(*) FROM applications WHERE id = %s;", (app_id,))
    res_a = cur.fetchone()[0]
    assert res_a == 1, f"User A should see their own application, got {res_a}"
    print("3.1 Applicant reading own application: PASS")

    # 3.2 Owner User B queries applications for their property
    cur.execute(f"SET app.current_user_id = '{user_b}';")
    cur.execute("SELECT count(*) FROM applications WHERE id = %s;", (app_id,))
    res_b = cur.fetchone()[0]
    assert res_b == 1, f"Owner User B should see application for their property, got {res_b}"
    print("3.2 Property Owner reading application: PASS")

    # 3.3 Outsider user queries applications
    cur.execute(f"SET app.current_user_id = '{outsider_u}';")
    cur.execute("SELECT count(*) FROM applications WHERE id = %s;", (app_id,))
    count = cur.fetchone()[0]
    assert count == 0, f"Outsider should see 0 applications, got {count}"
    print("3.3 Unauthorized outsider reading application: PASS (Denied / 0 rows returned)")

    print("\n--- 4. Testing RLS on Conversations & Messages ---")
    cur.execute("RESET ROLE;") # Reset to superuser to create conversation fixtures
    conv_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO conversations (id, type, status, context_metadata, created_at, last_message_at) "
        "VALUES (%s, 'direct', 'active', '{}', NOW(), NOW());",
        (conv_id,)
    )
    cur.execute(
        "INSERT INTO conversation_participants (id, conversation_id, user_id, role, is_active, joined_at) VALUES "
        "(%s, %s, %s, 'member', true, NOW()), (%s, %s, %s, 'member', true, NOW());",
        (str(uuid.uuid4()), conv_id, user_a, str(uuid.uuid4()), conv_id, user_b)
    )
    msg_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO messages (id, conversation_id, sender_id, content, message_type, metadata, is_edited, is_deleted, is_read, sent_at) "
        "VALUES (%s, %s, %s, 'Secret message', 'text', '{}', false, false, false, NOW());",
        (msg_id, conv_id, user_a)
    )
    conn.commit()

    # Re-assume unprivileged role
    cur.execute("SET ROLE rls_test_user;")

    # 4.1 Participant User A sees message
    cur.execute(f"SET app.current_user_id = '{user_a}';")
    cur.execute("SELECT count(*) FROM messages WHERE id = %s;", (msg_id,))
    assert cur.fetchone()[0] == 1
    print("4.1 Active participant reading message: PASS")

    # 4.2 Outsider queries messages
    cur.execute(f"SET app.current_user_id = '{outsider_u}';")
    cur.execute("SELECT count(*) FROM messages WHERE id = %s;", (msg_id,))
    out_count = cur.fetchone()[0]
    assert out_count == 0, f"Outsider saw {out_count} messages"
    print("4.2 Unauthorized outsider reading message: PASS (0 rows returned)")

    print("\n--- 5. Testing RLS on Notifications ---")
    cur.execute("RESET ROLE;")
    notif_a = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO notifications (id, user_id, title, body, notification_type, is_read, created_at) "
        "VALUES (%s, %s, 'Alert A', 'For user A only', 'system', false, NOW());",
        (notif_a, user_a)
    )
    conn.commit()

    cur.execute("SET ROLE rls_test_user;")
    # User B queries notifications
    cur.execute(f"SET app.current_user_id = '{user_b}';")
    cur.execute("SELECT count(*) FROM notifications WHERE id = %s;", (notif_a,))
    assert cur.fetchone()[0] == 0
    print("5.1 Notification isolation across users: PASS (User B cannot see User A alerts)")

    # User A queries notifications
    cur.execute(f"SET app.current_user_id = '{user_a}';")
    cur.execute("SELECT count(*) FROM notifications WHERE id = %s;", (notif_a,))
    assert cur.fetchone()[0] == 1
    print("5.2 Recipient reading own notification: PASS")

    print("\n--- 6. Testing RLS on Profile Updates ---")
    # Outsider attempts to update User A's profile
    cur.execute(f"SET app.current_user_id = '{outsider_u}';")
    cur.execute("UPDATE profiles SET bio = 'Hacked' WHERE user_id = %s;", (user_a,))
    # Since RLS policy has WITH CHECK (user_id = current_setting('app.current_user_id')),
    # 0 rows will be updated because USING clause filters it out
    assert cur.rowcount == 0, f"Expected 0 rows updated by outsider, got {cur.rowcount}"
    print("6.1 Cross-user profile modification attempt: PASS (0 rows updated / silently denied by RLS)")

    print("\n--- 7. Testing Anonymous Access Boundaries ---")
    # 7.1 Anonymous reads active properties
    cur.execute("RESET app.current_user_id;")
    cur.execute("SELECT count(*) FROM properties WHERE is_active = true;")
    anon_props = cur.fetchone()[0]
    assert anon_props >= 1, "Anonymous user should be able to view active properties"
    print(f"7.1 Anonymous property discovery: PASS ({anon_props} active properties visible)")

    # 7.2 Anonymous reading private applications
    cur.execute("SELECT count(*) FROM applications;")
    anon_apps = cur.fetchone()[0]
    assert anon_apps == 0, "Anonymous user must see 0 private applications"
    print("7.2 Anonymous application access: PASS (0 rows returned)")

    print("\n--- 8. Testing Unauthorized Deletion / Tampering ---")
    # Outsider attempts to delete User A's application
    cur.execute(f"SET app.current_user_id = '{outsider_u}';")
    cur.execute("DELETE FROM applications WHERE id = %s;", (app_id,))
    assert cur.rowcount == 0, "Outsider must not be able to delete User A's application"
    print("8.1 Unauthorized application deletion: PASS (0 rows deleted / blocked by RLS)")

    print("\n--- 9. Testing Group Syndicate Access Boundaries ---")
    cur.execute("RESET ROLE;")
    group_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO groups (id, creator_id, name, target_budget_total, target_city, created_at, updated_at) "
        "VALUES (%s, %s, 'Koramangala Flat Hunt', 50000, 'Bengaluru', NOW(), NOW());",
        (group_id, user_a)
    )
    cur.execute(
        "INSERT INTO group_members (id, group_id, user_id, role, joined_at) "
        "VALUES (%s, %s, %s, 'leader', NOW());",
        (str(uuid.uuid4()), group_id, user_a)
    )
    conn.commit()

    cur.execute("SET ROLE rls_test_user;")
    # Member User A reads group
    cur.execute(f"SET app.current_user_id = '{user_a}';")
    cur.execute("SELECT count(*) FROM groups WHERE id = %s;", (group_id,))
    assert cur.fetchone()[0] == 1
    print("9.1 Group member viewing group: PASS")

    # Outsider tries to modify group membership
    cur.execute(f"SET app.current_user_id = '{outsider_u}';")
    cur.execute("DELETE FROM group_members WHERE group_id = %s AND user_id = %s;", (group_id, user_a))
    assert cur.rowcount == 0
    print("9.2 Outsider tampering with group members: PASS (0 rows affected / denied)")

    cur.execute("RESET ROLE;")
    conn.commit()
    conn.close()
    print("\n=== ALL RLS NON-SUPERUSER TESTS PASSED 100% ===")

if __name__ == "__main__":
    run_rls_tests()
