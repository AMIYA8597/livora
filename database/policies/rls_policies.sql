-- ==============================================================================
-- SUPERSEDED - NOT APPLIED BY MIGRATIONS. Do not apply to Supabase.
-- Data API security is enforced by Alembic migration 005_lockdown_data_api
-- (RLS on every table + no anon/authenticated privileges). The FastAPI backend
-- is the only data path. This file is kept for the legacy scripts/test_rls_*.py
-- harnesses only. Known flaw: the users SELECT policy below exposes every active
-- user row (including hashed_password) to any role it is granted to.
-- ==============================================================================

-- ==============================================================================
-- Database Policies: Complete Row-Level Security (RLS) Configuration
-- Dual-Context Support: Supabase PostgREST (auth.uid) & FastAPI (app.current_user_id)
-- ==============================================================================

-- 0. Universal Current User Resolution Function
CREATE OR REPLACE FUNCTION current_auth_uid() RETURNS UUID AS $$
BEGIN
    -- Check for PostgREST / Supabase Auth context
    IF NULLIF(current_setting('request.jwt.claim.sub', true), '') IS NOT NULL THEN
        RETURN NULLIF(current_setting('request.jwt.claim.sub', true), '')::UUID;
    END IF;
    -- Check for FastAPI direct session context
    IF NULLIF(current_setting('app.current_user_id', true), '') IS NOT NULL THEN
        RETURN NULLIF(current_setting('app.current_user_id', true), '')::UUID;
    END IF;
    RETURN NULL;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

-- Check if current authenticated user is an administrator
CREATE OR REPLACE FUNCTION is_admin() RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM users 
        WHERE id = current_auth_uid() AND role = 'admin' AND is_active = true
    );
EXCEPTION WHEN OTHERS THEN
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql STABLE;

-- Security Definer helper to prevent RLS recursion on conversation participants
CREATE OR REPLACE FUNCTION user_in_conversation(cid UUID, uid UUID) RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM conversation_participants WHERE conversation_id = cid AND user_id = uid
    );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Security Definer helper to prevent RLS recursion on group members
CREATE OR REPLACE FUNCTION user_in_group(gid UUID, uid UUID) RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM group_members WHERE group_id = gid AND user_id = uid
    );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Enable Row-Level Security on Domain Tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_privacy_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE lifestyle_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_dealbreakers ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE beds ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_wishlist_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE moderation_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_blocks ENABLE ROW LEVEL SECURITY;

-- 1. Users & Privacy Settings
DROP POLICY IF EXISTS users_select_policy ON users;
CREATE POLICY users_select_policy ON users
    FOR SELECT
    USING (is_active = true OR id = current_auth_uid() OR is_admin());

DROP POLICY IF EXISTS users_update_policy ON users;
CREATE POLICY users_update_policy ON users
    FOR UPDATE
    USING (id = current_auth_uid() OR is_admin())
    WITH CHECK (id = current_auth_uid() OR is_admin());

DROP POLICY IF EXISTS user_privacy_settings_policy ON user_privacy_settings;
CREATE POLICY user_privacy_settings_policy ON user_privacy_settings
    FOR ALL
    USING (user_id = current_auth_uid() OR is_admin());

-- 2. Profiles & Lifestyle Preferences
DROP POLICY IF EXISTS profiles_select_policy ON profiles;
CREATE POLICY profiles_select_policy ON profiles
    FOR SELECT
    USING (true);

DROP POLICY IF EXISTS profiles_update_policy ON profiles;
CREATE POLICY profiles_update_policy ON profiles
    FOR UPDATE
    USING (user_id = current_auth_uid() OR is_admin())
    WITH CHECK (user_id = current_auth_uid() OR is_admin());

DROP POLICY IF EXISTS lifestyle_select_policy ON lifestyle_profiles;
CREATE POLICY lifestyle_select_policy ON lifestyle_profiles
    FOR SELECT
    USING (true);

DROP POLICY IF EXISTS lifestyle_modify_policy ON lifestyle_profiles;
CREATE POLICY lifestyle_modify_policy ON lifestyle_profiles
    FOR ALL
    USING (user_id = current_auth_uid() OR is_admin());

DROP POLICY IF EXISTS dealbreakers_policy ON user_dealbreakers;
CREATE POLICY dealbreakers_policy ON user_dealbreakers
    FOR ALL
    USING (user_id = current_auth_uid() OR is_admin());

-- 3. Properties & Inventory (Units, Rooms, Beds)
DROP POLICY IF EXISTS properties_select_policy ON properties;
CREATE POLICY properties_select_policy ON properties
    FOR SELECT
    USING (is_active = true OR owner_id = current_auth_uid() OR is_admin());

DROP POLICY IF EXISTS properties_modify_policy ON properties;
CREATE POLICY properties_modify_policy ON properties
    FOR ALL
    USING (owner_id = current_auth_uid() OR is_admin());

DROP POLICY IF EXISTS rooms_select_policy ON rooms;
CREATE POLICY rooms_select_policy ON rooms
    FOR SELECT
    USING (true);

DROP POLICY IF EXISTS rooms_modify_policy ON rooms;
CREATE POLICY rooms_modify_policy ON rooms
    FOR ALL
    USING (
        property_id IN (SELECT id FROM properties WHERE owner_id = current_auth_uid())
        OR is_admin()
    );

DROP POLICY IF EXISTS beds_select_policy ON beds;
CREATE POLICY beds_select_policy ON beds
    FOR SELECT
    USING (true);

DROP POLICY IF EXISTS beds_modify_policy ON beds;
CREATE POLICY beds_modify_policy ON beds
    FOR ALL
    USING (
        room_id IN (
            SELECT r.id FROM rooms r 
            JOIN properties p ON r.property_id = p.id 
            WHERE p.owner_id = current_auth_uid()
        )
        OR is_admin()
    );

-- 4. Rental Applications & Viewing Appointments
DROP POLICY IF EXISTS applications_select_policy ON applications;
CREATE POLICY applications_select_policy ON applications
    FOR SELECT
    USING (
        applicant_id = current_auth_uid()
        OR property_id IN (SELECT id FROM properties WHERE owner_id = current_auth_uid())
        OR is_admin()
    );

DROP POLICY IF EXISTS applications_insert_policy ON applications;
CREATE POLICY applications_insert_policy ON applications
    FOR INSERT
    WITH CHECK (applicant_id = current_auth_uid());

DROP POLICY IF EXISTS applications_update_policy ON applications;
CREATE POLICY applications_update_policy ON applications
    FOR UPDATE
    USING (
        applicant_id = current_auth_uid()
        OR property_id IN (SELECT id FROM properties WHERE owner_id = current_auth_uid())
        OR is_admin()
    );

DROP POLICY IF EXISTS appointments_select_policy ON appointments;
CREATE POLICY appointments_select_policy ON appointments
    FOR SELECT
    USING (
        applicant_id = current_auth_uid()
        OR property_id IN (SELECT id FROM properties WHERE owner_id = current_auth_uid())
        OR is_admin()
    );

DROP POLICY IF EXISTS appointments_modify_policy ON appointments;
CREATE POLICY appointments_modify_policy ON appointments
    FOR ALL
    USING (
        applicant_id = current_auth_uid()
        OR property_id IN (SELECT id FROM properties WHERE owner_id = current_auth_uid())
        OR is_admin()
    );

-- 5. Conversations, Participants, Messages & Attachments
DROP POLICY IF EXISTS conversations_select_policy ON conversations;
CREATE POLICY conversations_select_policy ON conversations
    FOR SELECT
    USING (
        user_in_conversation(id, current_auth_uid())
        OR is_admin()
    );

DROP POLICY IF EXISTS conversation_participants_select_policy ON conversation_participants;
CREATE POLICY conversation_participants_select_policy ON conversation_participants
    FOR SELECT
    USING (
        user_id = current_auth_uid()
        OR user_in_conversation(conversation_id, current_auth_uid())
        OR is_admin()
    );

DROP POLICY IF EXISTS messages_select_policy ON messages;
CREATE POLICY messages_select_policy ON messages
    FOR SELECT
    USING (
        user_in_conversation(conversation_id, current_auth_uid())
        OR is_admin()
    );

DROP POLICY IF EXISTS messages_insert_policy ON messages;
CREATE POLICY messages_insert_policy ON messages
    FOR INSERT
    WITH CHECK (
        sender_id = current_auth_uid()
        AND user_in_conversation(conversation_id, current_auth_uid())
    );

DROP POLICY IF EXISTS attachments_select_policy ON attachments;
CREATE POLICY attachments_select_policy ON attachments
    FOR SELECT
    USING (
        user_in_conversation(conversation_id, current_auth_uid())
        OR uploader_id = current_auth_uid()
        OR is_admin()
    );

-- 6. Groups, Members & Wishlists
DROP POLICY IF EXISTS groups_select_policy ON groups;
CREATE POLICY groups_select_policy ON groups
    FOR SELECT
    USING (
        user_in_group(id, current_auth_uid())
        OR creator_id = current_auth_uid()
        OR is_admin()
    );

DROP POLICY IF EXISTS group_members_select_policy ON group_members;
CREATE POLICY group_members_select_policy ON group_members
    FOR SELECT
    USING (
        user_id = current_auth_uid()
        OR user_in_group(group_id, current_auth_uid())
        OR is_admin()
    );

DROP POLICY IF EXISTS group_wishlist_policy ON group_wishlist_items;
CREATE POLICY group_wishlist_policy ON group_wishlist_items
    FOR ALL
    USING (
        user_in_group(group_id, current_auth_uid())
        OR is_admin()
    );

-- 7. Notifications (Strict Personal Isolation)
DROP POLICY IF EXISTS notifications_isolation_policy ON notifications;
CREATE POLICY notifications_isolation_policy ON notifications
    FOR ALL
    USING (user_id = current_auth_uid() OR is_admin());

-- 8. Trust, Verification & Moderation
DROP POLICY IF EXISTS verifications_select_policy ON verifications;
CREATE POLICY verifications_select_policy ON verifications
    FOR SELECT
    USING (user_id = current_auth_uid() OR is_admin());

DROP POLICY IF EXISTS verifications_insert_policy ON verifications;
CREATE POLICY verifications_insert_policy ON verifications
    FOR INSERT
    WITH CHECK (user_id = current_auth_uid() OR is_admin());

DROP POLICY IF EXISTS moderation_reports_policy ON moderation_reports;
CREATE POLICY moderation_reports_policy ON moderation_reports
    FOR SELECT
    USING (reporter_id = current_auth_uid() OR is_admin());

DROP POLICY IF EXISTS moderation_reports_insert_policy ON moderation_reports;
CREATE POLICY moderation_reports_insert_policy ON moderation_reports
    FOR INSERT
    WITH CHECK (reporter_id = current_auth_uid());

DROP POLICY IF EXISTS user_blocks_policy ON user_blocks;
CREATE POLICY user_blocks_policy ON user_blocks
    FOR ALL
    USING (user_id = current_auth_uid() OR is_admin());
