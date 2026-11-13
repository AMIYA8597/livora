-- ==============================================================================
-- Migration 001: Initial Schema for Flatmate Platform
-- ==============================================================================

-- Enable Core Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    phone_number VARCHAR(32),
    role VARCHAR(32) NOT NULL DEFAULT 'seeker' CHECK (role IN ('seeker', 'owner', 'admin')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Profiles & Lifestyle Vectors
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    display_name VARCHAR(100) NOT NULL,
    avatar_url TEXT,
    bio TEXT,
    birth_date DATE,
    gender VARCHAR(32) CHECK (gender IN ('male', 'female', 'non_binary', 'other', 'prefer_not_to_say')),
    occupation VARCHAR(100),
    budget_min INTEGER NOT NULL DEFAULT 500,
    budget_max INTEGER NOT NULL DEFAULT 2500,
    move_in_date DATE,
    lease_duration_months INTEGER DEFAULT 12,
    lifestyle_vector vector(64) NOT NULL,
    lifestyle_traits JSONB NOT NULL DEFAULT '{}'::jsonb,
    preferred_locations TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Properties Table with PostGIS Location
CREATE TABLE IF NOT EXISTS properties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    property_type VARCHAR(50) NOT NULL CHECK (property_type IN ('apartment', 'house', 'condo', 'studio', 'townhouse')),
    location GEOMETRY(Point, 4326) NOT NULL,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100),
    postal_code VARCHAR(20) NOT NULL,
    country VARCHAR(100) NOT NULL DEFAULT 'USA',
    monthly_rent DECIMAL(10, 2) NOT NULL,
    deposit DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    bills_included BOOLEAN NOT NULL DEFAULT false,
    total_bedrooms INTEGER NOT NULL DEFAULT 1,
    total_bathrooms INTEGER NOT NULL DEFAULT 1,
    available_from DATE NOT NULL,
    is_furnished BOOLEAN NOT NULL DEFAULT false,
    pets_allowed BOOLEAN NOT NULL DEFAULT false,
    smoking_allowed BOOLEAN NOT NULL DEFAULT false,
    images TEXT[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Rooms within Properties
CREATE TABLE IF NOT EXISTS rooms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    room_name VARCHAR(100) NOT NULL,
    room_type VARCHAR(50) NOT NULL CHECK (room_type IN ('private', 'shared', 'master_ensuite')),
    room_rent DECIMAL(10, 2) NOT NULL,
    deposit DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    private_bath BOOLEAN NOT NULL DEFAULT false,
    is_available BOOLEAN NOT NULL DEFAULT true,
    available_from DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Property Amenities
CREATE TABLE IF NOT EXISTS property_amenities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    amenity_key VARCHAR(50) NOT NULL,
    UNIQUE(property_id, amenity_key)
);

-- 6. Flatmate Groups (Hunting Syndicates)
CREATE TABLE IF NOT EXISTS groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    target_budget_total INTEGER NOT NULL,
    target_city VARCHAR(100) NOT NULL,
    target_move_in DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Group Members
CREATE TABLE IF NOT EXISTS group_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL DEFAULT 'member' CHECK (role IN ('leader', 'member', 'pending')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(group_id, user_id)
);

-- 8. Group Wishlist & Property Voting
CREATE TABLE IF NOT EXISTS group_wishlist_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    added_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    votes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(group_id, property_id)
);

-- 9. Rental Applications
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    applicant_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id UUID REFERENCES groups(id) ON DELETE SET NULL,
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    room_id UUID REFERENCES rooms(id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'submitted' CHECK (status IN ('draft', 'submitted', 'reviewing', 'accepted', 'rejected', 'withdrawn')),
    introduction TEXT NOT NULL,
    proposed_rent DECIMAL(10, 2) NOT NULL,
    move_in_target DATE NOT NULL,
    documents TEXT[] NOT NULL DEFAULT '{}',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. Conversations & Messaging
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type VARCHAR(32) NOT NULL DEFAULT 'direct' CHECK (type IN ('direct', 'group', 'property_inquiry')),
    property_id UUID REFERENCES properties(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversation_participants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(conversation_id, user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    message_type VARCHAR(32) NOT NULL DEFAULT 'text' CHECK (message_type IN ('text', 'image', 'property_card', 'application_update')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_read BOOLEAN NOT NULL DEFAULT false,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11. User Verifications
CREATE TABLE IF NOT EXISTS verifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    verification_type VARCHAR(50) NOT NULL CHECK (verification_type IN ('government_id', 'student_email', 'work_email', 'background_check')),
    status VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    document_url TEXT,
    trust_score_bonus INTEGER NOT NULL DEFAULT 25,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. Moderation Reports
CREATE TABLE IF NOT EXISTS moderation_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reporter_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_type VARCHAR(32) NOT NULL CHECK (target_type IN ('user', 'property', 'message')),
    target_id UUID NOT NULL,
    reason VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'under_investigation', 'resolved', 'dismissed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 13. Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    reference_id UUID,
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
