-- ==============================================================================
-- Migration 003: India-First Flatmate Marketplace Complete Relational Schema
-- ==============================================================================

-- 1. Multi-Role RBAC & Privacy Settings
CREATE TABLE IF NOT EXISTS user_roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, role)
);

CREATE TABLE IF NOT EXISTS user_privacy_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    show_phone_publicly BOOLEAN NOT NULL DEFAULT false,
    show_exact_location BOOLEAN NOT NULL DEFAULT false,
    allow_direct_messages BOOLEAN NOT NULL DEFAULT true,
    profile_visibility VARCHAR(32) NOT NULL DEFAULT 'public' CHECK (profile_visibility IN ('public', 'matched_only', 'private')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Professional Taxonomy
CREATE TABLE IF NOT EXISTS professional_domains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS professions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_id UUID NOT NULL REFERENCES professional_domains(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS designations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profession_id UUID NOT NULL REFERENCES professions(id) ON DELETE CASCADE,
    title VARCHAR(120) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- 3. Geography & PostGIS Localities
CREATE TABLE IF NOT EXISTS countries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(3) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    currency_code VARCHAR(3) NOT NULL DEFAULT 'INR',
    phone_code VARCHAR(8) NOT NULL DEFAULT '+91'
);

CREATE TABLE IF NOT EXISTS states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id UUID NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(10) NOT NULL
);

CREATE TABLE IF NOT EXISTS cities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    state_id UUID NOT NULL REFERENCES states(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    tier INTEGER NOT NULL DEFAULT 1,
    center_location GEOMETRY(Point, 4326)
);

CREATE TABLE IF NOT EXISTS localities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    city_id UUID NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    postal_code VARCHAR(12) NOT NULL,
    center_location GEOMETRY(Point, 4326) NOT NULL,
    boundary_geojson JSONB
);

-- 4. Lifestyle Profiles & Dealbreakers
CREATE TABLE IF NOT EXISTS lifestyle_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sleep_schedule VARCHAR(32) NOT NULL DEFAULT 'flexible',
    wake_time_typical VARCHAR(10),
    sleep_time_typical VARCHAR(10),
    work_arrangement VARCHAR(32) NOT NULL DEFAULT 'hybrid',
    cleanliness_level INTEGER NOT NULL DEFAULT 3 CHECK (cleanliness_level BETWEEN 1 AND 5),
    chore_philosophy VARCHAR(50) NOT NULL DEFAULT 'shared_roster',
    noise_tolerance VARCHAR(32) NOT NULL DEFAULT 'moderate',
    instrument_or_music BOOLEAN NOT NULL DEFAULT false,
    lighting_preference VARCHAR(32) NOT NULL DEFAULT 'dim',
    guests_policy VARCHAR(50) NOT NULL DEFAULT 'occasional_weekends',
    social_battery VARCHAR(32) NOT NULL DEFAULT 'balanced',
    diet_preference VARCHAR(32) NOT NULL DEFAULT 'omnivore',
    non_veg_cooking_allowed BOOLEAN NOT NULL DEFAULT true,
    cooks_at_home VARCHAR(32) NOT NULL DEFAULT 'sometimes',
    smoking VARCHAR(32) NOT NULL DEFAULT 'never',
    drinking VARCHAR(32) NOT NULL DEFAULT 'socially',
    pet_preference VARCHAR(32) NOT NULL DEFAULT 'cats_and_dogs_ok',
    preference_vector vector(64) NOT NULL,
    custom_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_dealbreakers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rule_key VARCHAR(50) NOT NULL,
    is_strict BOOLEAN NOT NULL DEFAULT true,
    expected_value VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Beds Table with Strict Occupancy Limits
CREATE TABLE IF NOT EXISTS beds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id UUID NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    bed_identifier VARCHAR(20) NOT NULL,
    is_occupied BOOLEAN NOT NULL DEFAULT false,
    current_occupant_id UUID REFERENCES users(id) ON DELETE SET NULL,
    monthly_rent DECIMAL(12, 2) NOT NULL,
    available_from DATE NOT NULL
);

-- 6. PG Management Buildings & Wings
CREATE TABLE IF NOT EXISTS pg_buildings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    property_id UUID UNIQUE NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    building_name VARCHAR(150) NOT NULL,
    pg_type VARCHAR(32) NOT NULL DEFAULT 'coed' CHECK (pg_type IN ('gents', 'ladies', 'coed')),
    total_floors INTEGER NOT NULL DEFAULT 3,
    food_included BOOLEAN NOT NULL DEFAULT true,
    meal_type VARCHAR(50) NOT NULL DEFAULT 'veg_and_non_veg',
    meals_served_per_day INTEGER NOT NULL DEFAULT 3,
    gate_closing_time VARCHAR(10) DEFAULT '22:30',
    notice_period_days INTEGER NOT NULL DEFAULT 30,
    biometric_entry BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pg_floors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pg_building_id UUID NOT NULL REFERENCES pg_buildings(id) ON DELETE CASCADE,
    floor_number INTEGER NOT NULL,
    gender_restriction VARCHAR(32) NOT NULL DEFAULT 'coed',
    total_rooms INTEGER NOT NULL DEFAULT 4
);

-- 7. Tenancy & Vacancy Records
CREATE TABLE IF NOT EXISTS tenant_memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    room_id UUID REFERENCES rooms(id) ON DELETE SET NULL,
    bed_id UUID REFERENCES beds(id) ON DELETE SET NULL,
    tenant_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lease_start DATE NOT NULL,
    lease_end DATE,
    monthly_rent DECIMAL(12, 2) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'notice_period', 'vacated', 'terminated')),
    is_primary_tenant BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS existing_tenant_vacancies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    room_id UUID NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    posted_by_tenant_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    vacant_from DATE NOT NULL,
    expected_rent DECIMAL(12, 2) NOT NULL,
    deposit_required DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    preferred_gender VARCHAR(32) NOT NULL DEFAULT 'any',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Viewing Appointments
CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    room_id UUID REFERENCES rooms(id) ON DELETE SET NULL,
    host_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    applicant_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    appointment_type VARCHAR(32) NOT NULL DEFAULT 'physical_visit' CHECK (appointment_type IN ('physical_visit', 'video_call')),
    status VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'completed', 'cancelled', 'rescheduled')),
    scheduled_at TIMESTAMPTZ NOT NULL,
    meeting_link VARCHAR(255),
    notes TEXT,
    cancellation_reason VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Mutual Matching & Interactions
CREATE TABLE IF NOT EXISTS match_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(32) NOT NULL CHECK (action IN ('like', 'pass', 'save', 'super_like')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, target_user_id)
);

CREATE TABLE IF NOT EXISTS mutual_matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_one_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_two_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    compatibility_score FLOAT NOT NULL,
    algorithm_version VARCHAR(32) NOT NULL DEFAULT 'v1.0-india-heuristic',
    score_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'matched' CHECK (status IN ('matched', 'unmatched', 'blocked')),
    matched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_one_id, user_two_id)
);

-- 10. Subscriptions & Payments
CREATE TABLE IF NOT EXISTS subscription_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    price_inr DECIMAL(10, 2) NOT NULL,
    duration_days INTEGER NOT NULL DEFAULT 30,
    features JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES subscription_plans(id) ON DELETE RESTRICT,
    status VARCHAR(32) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    status VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'successful', 'failed', 'refunded')),
    gateway_order_id VARCHAR(100),
    gateway_payment_id VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
