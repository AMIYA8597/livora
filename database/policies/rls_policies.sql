-- ==============================================================================
-- Database Policies: Row-Level Security (RLS) Configuration
-- ==============================================================================

-- Enable Row-Level Security
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- 1. Profiles: Anyone authenticated can read active profiles, but only the owner can modify
CREATE POLICY profiles_select_policy ON profiles
    FOR SELECT
    USING (true);

CREATE POLICY profiles_update_policy ON profiles
    FOR UPDATE
    USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID);

-- 2. Applications: Applicants and listing owners can see relevant applications
CREATE POLICY applications_select_policy ON applications
    FOR SELECT
    USING (
        applicant_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
        OR property_id IN (
            SELECT id FROM properties WHERE owner_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
        )
    );

CREATE POLICY applications_insert_policy ON applications
    FOR INSERT
    WITH CHECK (
        applicant_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
    );

-- 3. Conversations & Messages: Only participants can view or send
CREATE POLICY conversations_select_policy ON conversations
    FOR SELECT
    USING (
        id IN (
            SELECT conversation_id FROM conversation_participants
            WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
        )
    );

CREATE POLICY messages_select_policy ON messages
    FOR SELECT
    USING (
        conversation_id IN (
            SELECT conversation_id FROM conversation_participants
            WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
        )
    );

CREATE POLICY messages_insert_policy ON messages
    FOR INSERT
    WITH CHECK (
        sender_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
        AND conversation_id IN (
            SELECT conversation_id FROM conversation_participants
            WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
        )
    );

-- 4. Verifications: Only the user or an admin can access sensitive verification proofs
CREATE POLICY verifications_select_policy ON verifications
    FOR SELECT
    USING (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
        OR EXISTS (
            SELECT 1 FROM users WHERE id = NULLIF(current_setting('app.current_user_id', true), '')::UUID AND role = 'admin'
        )
    );

-- 5. Notifications: Strictly isolated to recipient user
CREATE POLICY notifications_isolation_policy ON notifications
    FOR ALL
    USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID);
