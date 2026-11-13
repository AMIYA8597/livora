-- ==============================================================================
-- Migration 002: Spatial, Vector, Trigram & Composite Performance Indexes
-- ==============================================================================

-- 1. Spatial GIST Index for Ultra-Fast Radius and Polygon Searches
CREATE INDEX IF NOT EXISTS idx_properties_location 
ON properties USING GIST (location);

-- 2. HNSW Index on pgvector for Cosine Similarity Searches
CREATE INDEX IF NOT EXISTS idx_profiles_lifestyle_vector 
ON profiles USING hnsw (lifestyle_vector vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 3. Trigram Fuzzy Search Indexes
CREATE INDEX IF NOT EXISTS idx_properties_city_trgm 
ON properties USING GIN (city gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_profiles_name_trgm 
ON profiles USING GIN (display_name gin_trgm_ops);

-- 4. B-Tree Lookup Indexes for Queries & Foreign Keys
CREATE INDEX IF NOT EXISTS idx_properties_owner_id ON properties (owner_id);
CREATE INDEX IF NOT EXISTS idx_properties_monthly_rent ON properties (monthly_rent);
CREATE INDEX IF NOT EXISTS idx_properties_available_from ON properties (available_from);
CREATE INDEX IF NOT EXISTS idx_properties_city_active ON properties (city, is_active);

CREATE INDEX IF NOT EXISTS idx_rooms_property_avail ON rooms (property_id, is_available);

CREATE INDEX IF NOT EXISTS idx_applications_applicant_id ON applications (applicant_id);
CREATE INDEX IF NOT EXISTS idx_applications_property_id ON applications (property_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications (status);

CREATE INDEX IF NOT EXISTS idx_conv_participants_user ON conversation_participants (user_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_sent ON messages (conversation_id, sent_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications (user_id, is_read);
