BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 001_initial_schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";;

CREATE EXTENSION IF NOT EXISTS "pg_trgm";;

CREATE EXTENSION IF NOT EXISTS postgis;;

CREATE TABLE users (
    id UUID NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    hashed_password VARCHAR(255) NOT NULL, 
    full_name VARCHAR(150) NOT NULL, 
    phone_number VARCHAR(32), 
    role VARCHAR(32) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    is_verified BOOLEAN NOT NULL, 
    phone_verified_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_users_phone_number ON users (phone_number);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE professional_domains (
    id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    slug VARCHAR(100) NOT NULL, 
    description TEXT, 
    is_active BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE UNIQUE INDEX ix_professional_domains_slug ON professional_domains (slug);

CREATE TABLE countries (
    id UUID NOT NULL, 
    code VARCHAR(3) NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    currency_code VARCHAR(3) NOT NULL, 
    phone_code VARCHAR(8) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE TABLE outbox_events (
    id UUID NOT NULL, 
    event_type VARCHAR(64) NOT NULL, 
    payload JSONB NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    retry_count INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    processed_at TIMESTAMP WITH TIME ZONE, 
    next_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_error TEXT, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_outbox_events_event_type ON outbox_events (event_type);

CREATE INDEX ix_outbox_events_status ON outbox_events (status);

CREATE INDEX ix_outbox_events_created_at ON outbox_events (created_at);

CREATE TABLE subscription_plans (
    id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    code VARCHAR(50) NOT NULL, 
    audience VARCHAR(16) NOT NULL, 
    description TEXT, 
    price_inr NUMERIC(10, 2) NOT NULL, 
    period VARCHAR(16) NOT NULL, 
    interval INTEGER NOT NULL, 
    duration_days INTEGER NOT NULL, 
    features JSONB NOT NULL, 
    razorpay_plan_id VARCHAR(64), 
    razorpay_plan_amount INTEGER, 
    sort_order INTEGER NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE TABLE billing_events (
    id UUID NOT NULL, 
    provider VARCHAR(16) NOT NULL, 
    event_id VARCHAR(100) NOT NULL, 
    event_type VARCHAR(64) NOT NULL, 
    payload JSONB NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    error TEXT, 
    received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    processed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    UNIQUE (event_id)
);

CREATE TABLE content_embeddings (
    id UUID NOT NULL, 
    entity_type VARCHAR(32) NOT NULL, 
    entity_id UUID NOT NULL, 
    model VARCHAR(80) NOT NULL, 
    embedding FLOAT(24)[] NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE ml_models (
    id UUID NOT NULL, 
    name VARCHAR(64) NOT NULL, 
    version INTEGER NOT NULL, 
    params JSONB NOT NULL, 
    metrics JSONB NOT NULL, 
    training_rows INTEGER NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE user_roles (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    role VARCHAR(32) NOT NULL, 
    is_verified BOOLEAN NOT NULL, 
    metadata JSONB NOT NULL, 
    granted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_user_role UNIQUE (user_id, role), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_user_roles_user_id ON user_roles (user_id);

CREATE TABLE user_privacy_settings (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    show_phone_publicly BOOLEAN NOT NULL, 
    show_exact_location BOOLEAN NOT NULL, 
    allow_direct_messages BOOLEAN NOT NULL, 
    profile_visibility VARCHAR(32) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (user_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE profiles (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    display_name VARCHAR(100) NOT NULL, 
    avatar_url TEXT, 
    bio TEXT, 
    birth_date DATE, 
    gender VARCHAR(32), 
    occupation VARCHAR(100), 
    education_institute VARCHAR(150), 
    education_degree VARCHAR(100), 
    company_name VARCHAR(150), 
    designation VARCHAR(100), 
    budget_min INTEGER NOT NULL, 
    budget_max INTEGER NOT NULL, 
    move_in_date DATE, 
    lease_duration_months INTEGER NOT NULL, 
    lifestyle_vector FLOAT[] NOT NULL, 
    lifestyle_traits JSONB NOT NULL, 
    preferred_locations VARCHAR[] NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (user_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE professions (
    id UUID NOT NULL, 
    domain_id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    slug VARCHAR(100) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(domain_id) REFERENCES professional_domains (id) ON DELETE CASCADE
);

CREATE INDEX ix_professions_domain_id ON professions (domain_id);

CREATE TABLE states (
    id UUID NOT NULL, 
    country_id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    code VARCHAR(10) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(country_id) REFERENCES countries (id) ON DELETE CASCADE
);

CREATE TABLE lifestyle_profiles (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    sleep_schedule VARCHAR(32) NOT NULL, 
    wake_time_typical VARCHAR(10), 
    sleep_time_typical VARCHAR(10), 
    work_arrangement VARCHAR(32) NOT NULL, 
    cleanliness_level INTEGER NOT NULL, 
    chore_philosophy VARCHAR(50) NOT NULL, 
    noise_tolerance VARCHAR(32) NOT NULL, 
    instrument_or_music BOOLEAN NOT NULL, 
    lighting_preference VARCHAR(32) NOT NULL, 
    guests_policy VARCHAR(50) NOT NULL, 
    social_battery VARCHAR(32) NOT NULL, 
    diet_preference VARCHAR(32) NOT NULL, 
    non_veg_cooking_allowed BOOLEAN NOT NULL, 
    cooks_at_home VARCHAR(32) NOT NULL, 
    smoking VARCHAR(32) NOT NULL, 
    drinking VARCHAR(32) NOT NULL, 
    pet_preference VARCHAR(32) NOT NULL, 
    preference_vector FLOAT[] NOT NULL, 
    custom_notes TEXT, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_lifestyle_profiles_user_id ON lifestyle_profiles (user_id);

CREATE TABLE user_dealbreakers (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    rule_key VARCHAR(50) NOT NULL, 
    is_strict BOOLEAN NOT NULL, 
    expected_value VARCHAR(100) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_user_dealbreakers_user_id ON user_dealbreakers (user_id);

CREATE TABLE properties (
    id UUID NOT NULL, 
    owner_id UUID NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    description TEXT NOT NULL, 
    property_category VARCHAR(50) NOT NULL, 
    configuration VARCHAR(50) NOT NULL, 
    location geometry(POINT,4326) NOT NULL, 
    address_display VARCHAR(255) NOT NULL, 
    address_exact VARCHAR(255) NOT NULL, 
    city VARCHAR(100) NOT NULL, 
    state VARCHAR(100), 
    postal_code VARCHAR(20) NOT NULL, 
    country VARCHAR(100) NOT NULL, 
    currency VARCHAR(3) NOT NULL, 
    monthly_rent NUMERIC(12, 2) NOT NULL, 
    security_deposit NUMERIC(12, 2) NOT NULL, 
    maintenance_monthly NUMERIC(10, 2) NOT NULL, 
    bills_included BOOLEAN NOT NULL, 
    total_bedrooms INTEGER NOT NULL, 
    total_bathrooms INTEGER NOT NULL, 
    max_capacity INTEGER NOT NULL, 
    current_occupants INTEGER NOT NULL, 
    available_from DATE NOT NULL, 
    is_furnished BOOLEAN NOT NULL, 
    furnishing_status VARCHAR(32) NOT NULL, 
    pets_allowed BOOLEAN NOT NULL, 
    smoking_allowed BOOLEAN NOT NULL, 
    is_verified BOOLEAN NOT NULL, 
    listing_status VARCHAR(32) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    images TEXT[] NOT NULL, 
    featured_until TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT chk_prop_capacity_overflow CHECK (current_occupants <= max_capacity), 
    CONSTRAINT chk_prop_rent_positive CHECK (monthly_rent >= 0), 
    FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_properties_owner_id ON properties (owner_id);

CREATE INDEX ix_properties_monthly_rent ON properties (monthly_rent);

CREATE INDEX ix_properties_featured_until ON properties (featured_until);

CREATE INDEX ix_properties_postal_code ON properties (postal_code);

CREATE INDEX ix_properties_city ON properties (city);

CREATE TABLE groups (
    id UUID NOT NULL, 
    creator_id UUID NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    description TEXT, 
    target_budget_total INTEGER NOT NULL, 
    target_city VARCHAR(100) NOT NULL, 
    target_move_in DATE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(creator_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE match_interactions (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    target_user_id UUID NOT NULL, 
    action VARCHAR(32) NOT NULL, 
    features JSONB, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_user_interaction UNIQUE (user_id, target_user_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(target_user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_match_interactions_target_user_id ON match_interactions (target_user_id);

CREATE INDEX ix_match_interactions_user_id ON match_interactions (user_id);

CREATE TABLE mutual_matches (
    id UUID NOT NULL, 
    user_one_id UUID NOT NULL, 
    user_two_id UUID NOT NULL, 
    compatibility_score FLOAT NOT NULL, 
    algorithm_version VARCHAR(32) NOT NULL, 
    score_breakdown JSONB NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    matched_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_mutual_match_pair UNIQUE (user_one_id, user_two_id), 
    FOREIGN KEY(user_one_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_two_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_mutual_matches_user_two_id ON mutual_matches (user_two_id);

CREATE INDEX ix_mutual_matches_user_one_id ON mutual_matches (user_one_id);

CREATE TABLE notifications (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    body TEXT NOT NULL, 
    notification_type VARCHAR(50) NOT NULL, 
    category VARCHAR(20) DEFAULT 'account' NOT NULL, 
    link VARCHAR(300), 
    reference_id UUID, 
    is_read BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_user_created ON notifications (user_id, created_at);

CREATE INDEX ix_notifications_is_read ON notifications (is_read);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE push_subscriptions (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    endpoint TEXT NOT NULL, 
    p256dh VARCHAR(200) NOT NULL, 
    auth VARCHAR(100) NOT NULL, 
    user_agent VARCHAR(300), 
    failure_count INTEGER DEFAULT '0' NOT NULL, 
    last_success_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (endpoint)
);

CREATE INDEX ix_push_subscriptions_user_id ON push_subscriptions (user_id);

CREATE TABLE notification_preferences (
    user_id UUID NOT NULL, 
    push_messages BOOLEAN DEFAULT 'true' NOT NULL, 
    push_matches BOOLEAN DEFAULT 'true' NOT NULL, 
    push_rentals BOOLEAN DEFAULT 'true' NOT NULL, 
    push_account BOOLEAN DEFAULT 'true' NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (user_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE verifications (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    verification_type VARCHAR(50) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    method VARCHAR(16) DEFAULT 'manual' NOT NULL, 
    document_url TEXT, 
    email_domain VARCHAR(255), 
    subject_hash VARCHAR(64), 
    code_hash VARCHAR(64), 
    attempts INTEGER DEFAULT '0' NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    trust_score_bonus INTEGER NOT NULL, 
    verified_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_verifications_approved_subject ON verifications (subject_hash) WHERE status = 'approved' AND subject_hash IS NOT NULL;

CREATE INDEX ix_verifications_user_created ON verifications (user_id, created_at);

CREATE INDEX ix_verifications_subject_created ON verifications (subject_hash, created_at);

CREATE INDEX ix_verifications_user_id ON verifications (user_id);

CREATE TABLE phone_verifications (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    phone_e164 VARCHAR(20) NOT NULL, 
    code_hash VARCHAR(64) NOT NULL, 
    attempts INTEGER NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    consumed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX idx_phone_verifications_phone_created ON phone_verifications (phone_e164, created_at);

CREATE INDEX idx_phone_verifications_user_created ON phone_verifications (user_id, created_at);

CREATE TABLE moderation_reports (
    id UUID NOT NULL, 
    reporter_id UUID, 
    target_type VARCHAR(32) NOT NULL, 
    target_id UUID NOT NULL, 
    reason VARCHAR(100) NOT NULL, 
    description TEXT, 
    status VARCHAR(32) NOT NULL, 
    source VARCHAR(16) NOT NULL, 
    details JSONB, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(reporter_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE user_blocks (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    blocked_user_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_user_block UNIQUE (user_id, blocked_user_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(blocked_user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_user_blocks_blocked_user_id ON user_blocks (blocked_user_id);

CREATE INDEX ix_user_blocks_user_id ON user_blocks (user_id);

CREATE TABLE subscriptions (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    plan_id UUID NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    provider VARCHAR(16) NOT NULL, 
    provider_subscription_id VARCHAR(64), 
    short_url VARCHAR(255), 
    started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    current_start TIMESTAMP WITH TIME ZONE, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    cancel_at_period_end BOOLEAN NOT NULL, 
    cancelled_at TIMESTAMP WITH TIME ZONE, 
    provider_event_at BIGINT, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(plan_id) REFERENCES subscription_plans (id) ON DELETE RESTRICT, 
    UNIQUE (provider_subscription_id)
);

CREATE INDEX ix_subscriptions_user_id ON subscriptions (user_id);

CREATE TABLE designations (
    id UUID NOT NULL, 
    profession_id UUID NOT NULL, 
    title VARCHAR(120) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(profession_id) REFERENCES professions (id) ON DELETE CASCADE
);

CREATE INDEX ix_designations_profession_id ON designations (profession_id);

CREATE TABLE cities (
    id UUID NOT NULL, 
    state_id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    slug VARCHAR(100) NOT NULL, 
    tier INTEGER NOT NULL, 
    center_location geometry(POINT,4326), 
    PRIMARY KEY (id), 
    FOREIGN KEY(state_id) REFERENCES states (id) ON DELETE CASCADE
);

CREATE INDEX ix_cities_name ON cities (name);

CREATE UNIQUE INDEX ix_cities_slug ON cities (slug);

CREATE TABLE rooms (
    id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    room_name VARCHAR(100) NOT NULL, 
    room_type VARCHAR(50) NOT NULL, 
    room_rent NUMERIC(12, 2) NOT NULL, 
    deposit NUMERIC(12, 2) NOT NULL, 
    private_bath BOOLEAN NOT NULL, 
    attached_balcony BOOLEAN NOT NULL, 
    max_beds INTEGER NOT NULL, 
    occupied_beds INTEGER NOT NULL, 
    is_available BOOLEAN NOT NULL, 
    available_from DATE NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT chk_room_bed_capacity CHECK (occupied_beds <= max_beds), 
    FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE
);

CREATE INDEX ix_rooms_property_id ON rooms (property_id);

CREATE TABLE property_amenities (
    id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    amenity_key VARCHAR(50) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE
);

CREATE TABLE pg_buildings (
    id UUID NOT NULL, 
    operator_id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    building_name VARCHAR(150) NOT NULL, 
    pg_type VARCHAR(32) NOT NULL, 
    total_floors INTEGER NOT NULL, 
    food_included BOOLEAN NOT NULL, 
    meal_type VARCHAR(50) NOT NULL, 
    meals_served_per_day INTEGER NOT NULL, 
    gate_closing_time VARCHAR(10), 
    notice_period_days INTEGER NOT NULL, 
    biometric_entry BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(operator_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (property_id), 
    FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE
);

CREATE INDEX ix_pg_buildings_operator_id ON pg_buildings (operator_id);

CREATE TABLE group_members (
    id UUID NOT NULL, 
    group_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    role VARCHAR(32) NOT NULL, 
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_group_user UNIQUE (group_id, user_id), 
    FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE group_wishlist_items (
    id UUID NOT NULL, 
    group_id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    added_by UUID NOT NULL, 
    votes JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_group_property UNIQUE (group_id, property_id), 
    FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE, 
    FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE, 
    FOREIGN KEY(added_by) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE payments (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    subscription_id UUID, 
    amount NUMERIC(12, 2) NOT NULL, 
    currency VARCHAR(3) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    provider VARCHAR(16) NOT NULL, 
    method VARCHAR(32), 
    gateway_order_id VARCHAR(100), 
    gateway_payment_id VARCHAR(100), 
    gateway_invoice_id VARCHAR(100), 
    failure_reason VARCHAR(255), 
    paid_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(subscription_id) REFERENCES subscriptions (id) ON DELETE SET NULL, 
    UNIQUE (gateway_payment_id)
);

CREATE INDEX ix_payments_user_id ON payments (user_id);

CREATE TABLE localities (
    id UUID NOT NULL, 
    city_id UUID NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    postal_code VARCHAR(12) NOT NULL, 
    center_location geometry(POINT,4326) NOT NULL, 
    boundary_geojson JSONB, 
    PRIMARY KEY (id), 
    FOREIGN KEY(city_id) REFERENCES cities (id) ON DELETE CASCADE
);

CREATE INDEX ix_localities_postal_code ON localities (postal_code);

CREATE INDEX ix_localities_city_id ON localities (city_id);

CREATE INDEX ix_localities_name ON localities (name);

CREATE TABLE beds (
    id UUID NOT NULL, 
    room_id UUID NOT NULL, 
    bed_identifier VARCHAR(20) NOT NULL, 
    is_occupied BOOLEAN NOT NULL, 
    current_occupant_id UUID, 
    monthly_rent NUMERIC(12, 2) NOT NULL, 
    available_from DATE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE CASCADE, 
    FOREIGN KEY(current_occupant_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_beds_room_id ON beds (room_id);

CREATE TABLE existing_tenant_vacancies (
    id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    room_id UUID NOT NULL, 
    posted_by_tenant_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    description TEXT NOT NULL, 
    vacant_from DATE NOT NULL, 
    expected_rent NUMERIC(12, 2) NOT NULL, 
    deposit_required NUMERIC(12, 2) NOT NULL, 
    preferred_gender VARCHAR(32) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE, 
    FOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE CASCADE, 
    FOREIGN KEY(posted_by_tenant_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_existing_tenant_vacancies_property_id ON existing_tenant_vacancies (property_id);

CREATE TABLE pg_floors (
    id UUID NOT NULL, 
    pg_building_id UUID NOT NULL, 
    floor_number INTEGER NOT NULL, 
    gender_restriction VARCHAR(32) NOT NULL, 
    total_rooms INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(pg_building_id) REFERENCES pg_buildings (id) ON DELETE CASCADE
);

CREATE INDEX ix_pg_floors_pg_building_id ON pg_floors (pg_building_id);

CREATE TABLE appointments (
    id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    room_id UUID, 
    host_id UUID NOT NULL, 
    applicant_id UUID NOT NULL, 
    appointment_type VARCHAR(32) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    meeting_link VARCHAR(255), 
    notes TEXT, 
    cancellation_reason VARCHAR(255), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE, 
    FOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE SET NULL, 
    FOREIGN KEY(host_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(applicant_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_appointments_property_id ON appointments (property_id);

CREATE TABLE applications (
    id UUID NOT NULL, 
    applicant_id UUID NOT NULL, 
    group_id UUID, 
    property_id UUID NOT NULL, 
    room_id UUID, 
    status VARCHAR(32) NOT NULL, 
    introduction TEXT NOT NULL, 
    proposed_rent NUMERIC(10, 2) NOT NULL, 
    move_in_target DATE NOT NULL, 
    documents TEXT[] NOT NULL, 
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(applicant_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE SET NULL, 
    FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE, 
    FOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE SET NULL
);

CREATE INDEX ix_applications_status ON applications (status);

CREATE INDEX ix_applications_property_id ON applications (property_id);

CREATE INDEX ix_applications_applicant_id ON applications (applicant_id);

CREATE TABLE tenant_memberships (
    id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    room_id UUID, 
    bed_id UUID, 
    tenant_id UUID NOT NULL, 
    lease_start DATE NOT NULL, 
    lease_end DATE, 
    monthly_rent NUMERIC(12, 2) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    is_primary_tenant BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE, 
    FOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE SET NULL, 
    FOREIGN KEY(bed_id) REFERENCES beds (id) ON DELETE SET NULL, 
    FOREIGN KEY(tenant_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_tenant_memberships_tenant_id ON tenant_memberships (tenant_id);

CREATE INDEX ix_tenant_memberships_property_id ON tenant_memberships (property_id);

CREATE TABLE application_status_events (
    id UUID NOT NULL, 
    application_id UUID NOT NULL, 
    actor_id UUID, 
    from_status VARCHAR(32) NOT NULL, 
    to_status VARCHAR(32) NOT NULL, 
    note TEXT, 
    by_staff BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE CASCADE, 
    FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_application_status_events_app_created ON application_status_events (application_id, created_at);

CREATE TABLE conversations (
    id UUID NOT NULL, 
    type VARCHAR(32) NOT NULL, 
    title VARCHAR(255), 
    property_id UUID, 
    application_id UUID, 
    group_id UUID, 
    flatmate_match_id UUID, 
    status VARCHAR(32) NOT NULL, 
    context_metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    last_message_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE SET NULL, 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE SET NULL, 
    FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE SET NULL, 
    FOREIGN KEY(flatmate_match_id) REFERENCES mutual_matches (id) ON DELETE SET NULL
);

CREATE INDEX ix_conversations_property_id ON conversations (property_id);

CREATE INDEX ix_conversations_last_message_at ON conversations (last_message_at);

CREATE INDEX ix_conversations_flatmate_match_id ON conversations (flatmate_match_id);

CREATE INDEX ix_conversations_group_id ON conversations (group_id);

CREATE INDEX ix_conversations_application_id ON conversations (application_id);

CREATE TABLE conversation_participants (
    id UUID NOT NULL, 
    conversation_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    role VARCHAR(32) NOT NULL, 
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    left_at TIMESTAMP WITH TIME ZONE, 
    is_active BOOLEAN NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_conv_user UNIQUE (conversation_id, user_id), 
    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX idx_conv_participant_active ON conversation_participants (user_id, is_active);

CREATE INDEX ix_conversation_participants_conversation_id ON conversation_participants (conversation_id);

CREATE INDEX ix_conversation_participants_user_id ON conversation_participants (user_id);

CREATE TABLE messages (
    id UUID NOT NULL, 
    conversation_id UUID NOT NULL, 
    sender_id UUID NOT NULL, 
    content TEXT NOT NULL, 
    message_type VARCHAR(32) NOT NULL, 
    idempotency_key VARCHAR(64), 
    reply_to_message_id UUID, 
    is_edited BOOLEAN NOT NULL, 
    edited_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    metadata JSONB NOT NULL, 
    is_read BOOLEAN NOT NULL, 
    sent_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, 
    FOREIGN KEY(sender_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(reply_to_message_id) REFERENCES messages (id) ON DELETE SET NULL
);

CREATE INDEX idx_conv_messages_sent ON messages (conversation_id, sent_at);

CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);

CREATE INDEX ix_messages_sender_id ON messages (sender_id);

CREATE INDEX ix_messages_sent_at ON messages (sent_at);

CREATE INDEX ix_messages_idempotency_key ON messages (idempotency_key);

CREATE TABLE conversation_preferences (
    id UUID NOT NULL, 
    conversation_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    is_muted BOOLEAN NOT NULL, 
    muted_until TIMESTAMP WITH TIME ZONE, 
    is_archived BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_conv_user_pref UNIQUE (conversation_id, user_id), 
    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX idx_conv_pref_archived ON conversation_preferences (user_id, is_archived);

CREATE INDEX ix_conversation_preferences_user_id ON conversation_preferences (user_id);

CREATE INDEX ix_conversation_preferences_conversation_id ON conversation_preferences (conversation_id);

CREATE TABLE attachments (
    id UUID NOT NULL, 
    conversation_id UUID NOT NULL, 
    message_id UUID, 
    uploader_id UUID NOT NULL, 
    file_name VARCHAR(255) NOT NULL, 
    file_path VARCHAR(512) NOT NULL, 
    mime_type VARCHAR(100) NOT NULL, 
    file_size_bytes BIGINT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, 
    FOREIGN KEY(message_id) REFERENCES messages (id) ON DELETE CASCADE, 
    FOREIGN KEY(uploader_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_attachments_message_id ON attachments (message_id);

CREATE INDEX ix_attachments_conversation_id ON attachments (conversation_id);

CREATE INDEX ix_attachments_uploader_id ON attachments (uploader_id);

CREATE TABLE conversation_read_cursors (
    id UUID NOT NULL, 
    conversation_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    last_read_message_id UUID, 
    last_read_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_conv_read_cursor UNIQUE (conversation_id, user_id), 
    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(last_read_message_id) REFERENCES messages (id) ON DELETE SET NULL
);

CREATE INDEX ix_conversation_read_cursors_conversation_id ON conversation_read_cursors (conversation_id);

CREATE INDEX ix_conversation_read_cursors_user_id ON conversation_read_cursors (user_id);

INSERT INTO alembic_version (version_num) VALUES ('001_initial_schema') RETURNING alembic_version.version_num;

-- Running upgrade 001_initial_schema -> 002_messaging_realtime

DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'title') THEN
                ALTER TABLE conversations ADD COLUMN title VARCHAR(255) NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'application_id') THEN
                ALTER TABLE conversations ADD COLUMN application_id UUID NULL REFERENCES applications(id) ON DELETE SET NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'group_id') THEN
                ALTER TABLE conversations ADD COLUMN group_id UUID NULL REFERENCES groups(id) ON DELETE SET NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'flatmate_match_id') THEN
                ALTER TABLE conversations ADD COLUMN flatmate_match_id UUID NULL REFERENCES mutual_matches(id) ON DELETE SET NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'status') THEN
                ALTER TABLE conversations ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'active';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'context_metadata') THEN
                ALTER TABLE conversations ADD COLUMN context_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
            END IF;
        END $$;;

DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversation_participants' AND column_name = 'role') THEN
                ALTER TABLE conversation_participants ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'member';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversation_participants' AND column_name = 'left_at') THEN
                ALTER TABLE conversation_participants ADD COLUMN left_at TIMESTAMPTZ NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversation_participants' AND column_name = 'is_active') THEN
                ALTER TABLE conversation_participants ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
            END IF;
        END $$;;

DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'idempotency_key') THEN
                ALTER TABLE messages ADD COLUMN idempotency_key VARCHAR(64) NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'reply_to_message_id') THEN
                ALTER TABLE messages ADD COLUMN reply_to_message_id UUID NULL REFERENCES messages(id) ON DELETE SET NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'is_edited') THEN
                ALTER TABLE messages ADD COLUMN is_edited BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'edited_at') THEN
                ALTER TABLE messages ADD COLUMN edited_at TIMESTAMPTZ NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'is_deleted') THEN
                ALTER TABLE messages ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'deleted_at') THEN
                ALTER TABLE messages ADD COLUMN deleted_at TIMESTAMPTZ NULL;
            END IF;
        END $$;;

CREATE TABLE IF NOT EXISTS attachments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            message_id UUID NULL REFERENCES messages(id) ON DELETE CASCADE,
            uploader_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            file_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(512) NOT NULL,
            mime_type VARCHAR(100) NOT NULL,
            file_size_bytes BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

CREATE INDEX IF NOT EXISTS idx_attachments_conv ON attachments(conversation_id);

CREATE INDEX IF NOT EXISTS idx_attachments_msg ON attachments(message_id);

CREATE INDEX IF NOT EXISTS idx_attachments_uploader ON attachments(uploader_id);

CREATE TABLE IF NOT EXISTS conversation_read_cursors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            last_read_message_id UUID NULL REFERENCES messages(id) ON DELETE SET NULL,
            last_read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_conv_read_cursor UNIQUE (conversation_id, user_id)
        );

CREATE INDEX IF NOT EXISTS idx_read_cursor_user ON conversation_read_cursors(user_id, last_read_at);

CREATE TABLE IF NOT EXISTS conversation_preferences (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            is_muted BOOLEAN NOT NULL DEFAULT FALSE,
            muted_until TIMESTAMPTZ NULL,
            is_archived BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_conv_user_pref UNIQUE (conversation_id, user_id)
        );

CREATE INDEX IF NOT EXISTS idx_conv_pref_archived ON conversation_preferences(user_id, is_archived);

CREATE TABLE IF NOT EXISTS outbox_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type VARCHAR(64) NOT NULL,
            payload JSONB NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ NULL
        );

CREATE INDEX IF NOT EXISTS idx_outbox_status_created ON outbox_events(status, created_at);

UPDATE alembic_version SET version_num='002_messaging_realtime' WHERE alembic_version.version_num = '001_initial_schema';

-- Running upgrade 002_messaging_realtime -> 003_pgvector_matching

CREATE INDEX IF NOT EXISTS ix_profiles_budget_range ON profiles (budget_min, budget_max);

CREATE INDEX IF NOT EXISTS ix_user_blocks_user_id ON user_blocks (user_id);

CREATE INDEX IF NOT EXISTS ix_user_blocks_blocked_user_id ON user_blocks (blocked_user_id);

DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'vector' AND typtype = 'd') THEN
                DROP DOMAIN vector;
            END IF;
        END $$;;

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS lifestyle_embedding vector(64);

CREATE OR REPLACE FUNCTION profiles_sync_lifestyle_embedding() RETURNS trigger AS $$
        BEGIN
            IF NEW.lifestyle_vector IS NULL
               OR cardinality(NEW.lifestyle_vector) <> 64
               OR NOT EXISTS (SELECT 1 FROM unnest(NEW.lifestyle_vector) v WHERE v <> 0) THEN
                NEW.lifestyle_embedding := NULL;
            ELSE
                NEW.lifestyle_embedding := NEW.lifestyle_vector::vector(64);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;;

DROP TRIGGER IF EXISTS trg_profiles_sync_lifestyle_embedding ON profiles;

CREATE TRIGGER trg_profiles_sync_lifestyle_embedding
        BEFORE INSERT OR UPDATE OF lifestyle_vector ON profiles
        FOR EACH ROW EXECUTE FUNCTION profiles_sync_lifestyle_embedding();

UPDATE profiles SET lifestyle_vector = lifestyle_vector;

CREATE INDEX IF NOT EXISTS ix_profiles_lifestyle_embedding_hnsw ON profiles USING hnsw (lifestyle_embedding vector_cosine_ops);

UPDATE alembic_version SET version_num='003_pgvector_matching' WHERE alembic_version.version_num = '002_messaging_realtime';

-- Running upgrade 003_pgvector_matching -> 004_real_postgis_location

DO $$
        DECLARE r record;
        BEGIN
            -- Every column typed with the fake domain (properties.location,
            -- cities.center_location, localities.center_location) is detached to text first.
            FOR r IN
                SELECT c.relname AS tbl, a.attname AS col
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_type t ON t.oid = a.atttypid
                WHERE t.typname = 'geometry' AND t.typtype = 'd' AND c.relkind = 'r' AND NOT a.attisdropped
            LOOP
                EXECUTE format('ALTER TABLE %I ALTER COLUMN %I TYPE text USING %I::text', r.tbl, r.col, r.col);
            END LOOP;

            FOR r IN
                SELECT p.oid::regprocedure AS sig
                FROM pg_proc p JOIN pg_language l ON l.oid = p.prolang
                WHERE l.lanname = 'plpgsql' AND p.proname IN ('st_asewkb', 'st_geomfromewkt')
            LOOP
                EXECUTE 'DROP FUNCTION ' || r.sig;
            END LOOP;

            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'geometry' AND typtype = 'd') THEN
                DROP DOMAIN geometry;
            END IF;
        END $$;;

CREATE EXTENSION IF NOT EXISTS postgis;

DO $$
        DECLARE
            spec record;
            coltype text;
        BEGIN
            FOR spec IN
                SELECT * FROM (VALUES
                    ('properties', 'location'),
                    ('cities', 'center_location'),
                    ('localities', 'center_location')
                ) AS v(tbl, col)
            LOOP
                SELECT format_type(a.atttypid, a.atttypmod) INTO coltype
                FROM pg_attribute a
                WHERE a.attrelid = spec.tbl::regclass AND a.attname = spec.col AND NOT a.attisdropped;

                IF coltype = 'text' THEN
                    EXECUTE format(
                        'ALTER TABLE %I ALTER COLUMN %I TYPE geometry(Point, 4326) '
                        'USING ST_SetSRID(ST_GeomFromEWKT(%I), 4326)', spec.tbl, spec.col, spec.col);
                ELSIF coltype = 'geometry' THEN
                    EXECUTE format(
                        'ALTER TABLE %I ALTER COLUMN %I TYPE geometry(Point, 4326) '
                        'USING ST_SetSRID(%I, 4326)', spec.tbl, spec.col, spec.col);
                END IF;
            END LOOP;
        END $$;;

CREATE INDEX IF NOT EXISTS ix_properties_location_geog ON properties USING gist ((location::geography));

UPDATE alembic_version SET version_num='004_real_postgis_location' WHERE alembic_version.version_num = '003_pgvector_matching';

-- Running upgrade 004_real_postgis_location -> 005_lockdown_data_api

DO $$
DECLARE
    r record;
    api_role text;
BEGIN
    -- 1. Default-deny RLS on every application table.
    FOR r IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend d
              WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e'
          )
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.relname);
    END LOOP;

    -- 2. Remove Data API access for Supabase's API roles, now and for future objects.
    FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', api_role);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', api_role);
            EXECUTE format('REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM %I', api_role);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', api_role);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', api_role);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM %I', api_role);
        END IF;
    END LOOP;
END $$;;

UPDATE alembic_version SET version_num='005_lockdown_data_api' WHERE alembic_version.version_num = '004_real_postgis_location';

-- Running upgrade 005_lockdown_data_api -> 006_outbox_dispatch

ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(), ADD COLUMN IF NOT EXISTS last_error TEXT;

CREATE INDEX IF NOT EXISTS idx_outbox_pending_due ON outbox_events (next_attempt_at) WHERE status = 'pending';

UPDATE alembic_version SET version_num='006_outbox_dispatch' WHERE alembic_version.version_num = '005_lockdown_data_api';

-- Running upgrade 006_outbox_dispatch -> 007_least_privilege_app_role

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'flatmate_app') THEN
        CREATE ROLE flatmate_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END $$;;

DO $$
DECLARE
    r record;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'flatmate_app') THEN
        RETURN;
    END IF;

    EXECUTE 'GRANT USAGE ON SCHEMA public TO flatmate_app';

    -- Only touch what is missing: ALTER/GRANT take table locks, so a steady-state run
    -- (every deploy) must not lock every table.
    FOR r IN
        SELECT c.relname, c.relrowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend d
              WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e'
          )
    LOOP
        IF NOT r.relrowsecurity THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.relname);
        END IF;
        IF r.relname = 'alembic_version' THEN
            IF has_table_privilege('flatmate_app', format('public.%I', r.relname), 'INSERT, UPDATE, DELETE, TRUNCATE') THEN
                EXECUTE format('REVOKE ALL ON public.%I FROM flatmate_app', r.relname);
            END IF;
            IF NOT has_table_privilege('flatmate_app', format('public.%I', r.relname), 'SELECT') THEN
                EXECUTE format('GRANT SELECT ON public.%I TO flatmate_app', r.relname);
            END IF;
        ELSIF NOT (
            has_table_privilege('flatmate_app', format('public.%I', r.relname), 'SELECT')
            AND has_table_privilege('flatmate_app', format('public.%I', r.relname), 'INSERT')
            AND has_table_privilege('flatmate_app', format('public.%I', r.relname), 'UPDATE')
            AND has_table_privilege('flatmate_app', format('public.%I', r.relname), 'DELETE')
        ) THEN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO flatmate_app', r.relname);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public' AND tablename = r.relname AND policyname = 'flatmate_app_all'
        ) THEN
            EXECUTE format(
                'CREATE POLICY flatmate_app_all ON public.%I FOR ALL TO flatmate_app USING (true) WITH CHECK (true)',
                r.relname
            );
        END IF;
    END LOOP;

    EXECUTE 'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO flatmate_app';

    -- Objects created later by the migrating role get the same grants.
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO flatmate_app';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO flatmate_app';
END $$;;

UPDATE alembic_version SET version_num='007_least_privilege_app_role' WHERE alembic_version.version_num = '006_outbox_dispatch';

-- Running upgrade 007_least_privilege_app_role -> 008_phone_verification

ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS phone_verifications (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            phone_e164 VARCHAR(20) NOT NULL,
            code_hash VARCHAR(64) NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            expires_at TIMESTAMPTZ NOT NULL,
            consumed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

CREATE INDEX IF NOT EXISTS idx_phone_verifications_user_created ON phone_verifications (user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_phone_verifications_phone_created ON phone_verifications (phone_e164, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_verified_phone ON users (phone_number) WHERE phone_verified_at IS NOT NULL;

UPDATE alembic_version SET version_num='008_phone_verification' WHERE alembic_version.version_num = '007_least_privilege_app_role';

-- Running upgrade 008_phone_verification -> 009_ml_platform

CREATE TABLE IF NOT EXISTS content_embeddings (
            id UUID PRIMARY KEY,
            entity_type VARCHAR(32) NOT NULL,
            entity_id UUID NOT NULL,
            model VARCHAR(80) NOT NULL,
            embedding REAL[] NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_content_embeddings_entity UNIQUE (entity_type, entity_id),
            CONSTRAINT ck_content_embeddings_type CHECK (entity_type IN ('property', 'profile'))
        );

CREATE INDEX IF NOT EXISTS ix_content_embeddings_type_model ON content_embeddings (entity_type, model);

ALTER TABLE properties ADD COLUMN IF NOT EXISTS search_tsv tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(address_display, '') || ' ' || coalesce(city, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'C')
        ) STORED;

CREATE INDEX IF NOT EXISTS ix_properties_search_tsv ON properties USING gin (search_tsv);

CREATE TABLE IF NOT EXISTS ml_models (
            id UUID PRIMARY KEY,
            name VARCHAR(64) NOT NULL,
            version INTEGER NOT NULL,
            params JSONB NOT NULL,
            metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
            training_rows INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_ml_models_name_version UNIQUE (name, version)
        );

CREATE UNIQUE INDEX IF NOT EXISTS uq_ml_models_one_active ON ml_models (name) WHERE is_active;

ALTER TABLE match_interactions ADD COLUMN IF NOT EXISTS features JSONB;

ALTER TABLE moderation_reports ALTER COLUMN reporter_id DROP NOT NULL;

ALTER TABLE moderation_reports ADD COLUMN IF NOT EXISTS source VARCHAR(16) NOT NULL DEFAULT 'user';

ALTER TABLE moderation_reports ADD COLUMN IF NOT EXISTS details JSONB;

CREATE UNIQUE INDEX IF NOT EXISTS uq_moderation_reports_auto_target ON moderation_reports (target_type, target_id) WHERE source = 'auto';

DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'vector' AND typtype = 'd') THEN
                DROP DOMAIN vector;
            END IF;
        END $$;;

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE content_embeddings ADD COLUMN IF NOT EXISTS embedding_vec vector(512);

CREATE OR REPLACE FUNCTION content_embeddings_sync_vec() RETURNS trigger AS $$
        BEGIN
            IF cardinality(NEW.embedding) = 512 THEN
                NEW.embedding_vec := NEW.embedding::vector(512);
            ELSE
                NEW.embedding_vec := NULL;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;;

DROP TRIGGER IF EXISTS trg_content_embeddings_sync_vec ON content_embeddings;

CREATE TRIGGER trg_content_embeddings_sync_vec
        BEFORE INSERT OR UPDATE OF embedding ON content_embeddings
        FOR EACH ROW EXECUTE FUNCTION content_embeddings_sync_vec();

UPDATE content_embeddings SET embedding = embedding;

CREATE INDEX IF NOT EXISTS ix_content_embeddings_vec_hnsw ON content_embeddings USING hnsw (embedding_vec vector_cosine_ops);

UPDATE alembic_version SET version_num='009_ml_platform' WHERE alembic_version.version_num = '008_phone_verification';

-- Running upgrade 009_ml_platform -> 010_billing

ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS audience VARCHAR(16) NOT NULL DEFAULT 'seeker';

ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS description TEXT;

ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS period VARCHAR(16) NOT NULL DEFAULT 'monthly';

ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS interval INTEGER NOT NULL DEFAULT 1;

ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS razorpay_plan_id VARCHAR(64);

ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS razorpay_plan_amount INTEGER;

ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS provider VARCHAR(16) NOT NULL DEFAULT 'razorpay';

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS provider_subscription_id VARCHAR(64);

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS short_url VARCHAR(255);

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS current_start TIMESTAMPTZ;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancel_at_period_end BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS provider_event_at BIGINT;

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE subscriptions ALTER COLUMN expires_at DROP NOT NULL;

ALTER TABLE subscriptions ALTER COLUMN status SET DEFAULT 'created';

CREATE UNIQUE INDEX IF NOT EXISTS subscriptions_provider_subscription_id_key ON subscriptions (provider_subscription_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_one_open_per_plan ON subscriptions (user_id, plan_id) WHERE status IN ('created', 'authenticated', 'active', 'pending');

CREATE INDEX IF NOT EXISTS ix_subscriptions_user_expires ON subscriptions (user_id, expires_at);

ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider VARCHAR(16) NOT NULL DEFAULT 'razorpay';

ALTER TABLE payments ADD COLUMN IF NOT EXISTS method VARCHAR(32);

ALTER TABLE payments ADD COLUMN IF NOT EXISTS gateway_invoice_id VARCHAR(100);

ALTER TABLE payments ADD COLUMN IF NOT EXISTS failure_reason VARCHAR(255);

ALTER TABLE payments ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS payments_gateway_payment_id_key ON payments (gateway_payment_id);

CREATE TABLE IF NOT EXISTS billing_events (
            id UUID PRIMARY KEY,
            provider VARCHAR(16) NOT NULL DEFAULT 'razorpay',
            event_id VARCHAR(100) NOT NULL UNIQUE,
            event_type VARCHAR(64) NOT NULL,
            payload JSONB NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'received',
            error TEXT,
            received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at TIMESTAMPTZ
        );

ALTER TABLE properties ADD COLUMN IF NOT EXISTS featured_until TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_properties_featured_until ON properties (featured_until);

INSERT INTO subscription_plans
            (id, name, code, audience, description, price_inr, period, interval, duration_days,
             features, sort_order, is_active, created_at)
        VALUES
            (gen_random_uuid(), 'Seeker Pro', 'seeker_pro', 'seeker',
             'See everyone who liked you and like without a daily limit.',
             199, 'monthly', 1, 30, '{"who_liked_me": true, "daily_likes": null}'::jsonb, 1, true, now()),
            (gen_random_uuid(), 'Owner Pro', 'owner_pro', 'owner',
             'Publish as many listings as you like and feature up to 3 at the top of search.',
             499, 'monthly', 1, 30, '{"max_active_listings": null, "featured_slots": 3}'::jsonb, 2, true, now())
        ON CONFLICT (code) DO NOTHING;

UPDATE alembic_version SET version_num='010_billing' WHERE alembic_version.version_num = '009_ml_platform';

-- Running upgrade 010_billing -> 011_email_verification

ALTER TABLE verifications ADD COLUMN IF NOT EXISTS method VARCHAR(16) NOT NULL DEFAULT 'manual';

ALTER TABLE verifications ADD COLUMN IF NOT EXISTS email_domain VARCHAR(255);

ALTER TABLE verifications ADD COLUMN IF NOT EXISTS subject_hash VARCHAR(64);

ALTER TABLE verifications ADD COLUMN IF NOT EXISTS code_hash VARCHAR(64);

ALTER TABLE verifications ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0;

ALTER TABLE verifications ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_verifications_user_created ON verifications (user_id, created_at);

CREATE INDEX IF NOT EXISTS ix_verifications_subject_created ON verifications (subject_hash, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS uq_verifications_approved_subject ON verifications (subject_hash) WHERE status = 'approved' AND subject_hash IS NOT NULL;

UPDATE verifications SET status = 'cancelled' WHERE status = 'pending' AND method = 'manual';

UPDATE users u SET is_verified = EXISTS (
               SELECT 1 FROM verifications v
               WHERE v.user_id = u.id AND v.status = 'approved' AND v.method <> 'manual'
                 AND v.verification_type IN ('work_email', 'student_email'))
           WHERE u.is_verified IS DISTINCT FROM EXISTS (
               SELECT 1 FROM verifications v
               WHERE v.user_id = u.id AND v.status = 'approved' AND v.method <> 'manual'
                 AND v.verification_type IN ('work_email', 'student_email'));

UPDATE alembic_version SET version_num='011_email_verification' WHERE alembic_version.version_num = '010_billing';

-- Running upgrade 011_email_verification -> 012_notifications_push

ALTER TABLE notifications ADD COLUMN IF NOT EXISTS category VARCHAR(20) NOT NULL DEFAULT 'account';

ALTER TABLE notifications ADD COLUMN IF NOT EXISTS link VARCHAR(300);

CREATE INDEX IF NOT EXISTS ix_notifications_user_created ON notifications (user_id, created_at);

UPDATE notifications SET category = CASE
               WHEN notification_type = 'new_message' THEN 'messages'
               WHEN notification_type IN ('match_created', 'new_interest') THEN 'matches'
               WHEN notification_type IN ('application_received', 'application_status_change', 'appointment_requested',
                                          'appointment_status_change', 'viewing_reminder', 'property_enquiry',
                                          'listing_expiry') THEN 'rentals'
               ELSE 'account' END
           WHERE category = 'account';

CREATE TABLE IF NOT EXISTS push_subscriptions (
               id UUID PRIMARY KEY,
               user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
               endpoint TEXT NOT NULL UNIQUE,
               p256dh VARCHAR(200) NOT NULL,
               auth VARCHAR(100) NOT NULL,
               user_agent VARCHAR(300),
               failure_count INTEGER NOT NULL DEFAULT 0,
               last_success_at TIMESTAMPTZ,
               created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
               updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
           );

CREATE INDEX IF NOT EXISTS ix_push_subscriptions_user_id ON push_subscriptions (user_id);

CREATE TABLE IF NOT EXISTS notification_preferences (
               user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
               push_messages BOOLEAN NOT NULL DEFAULT true,
               push_matches BOOLEAN NOT NULL DEFAULT true,
               push_rentals BOOLEAN NOT NULL DEFAULT true,
               push_account BOOLEAN NOT NULL DEFAULT true,
               updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
           );

UPDATE alembic_version SET version_num='012_notifications_push' WHERE alembic_version.version_num = '011_email_verification';

-- Running upgrade 012_notifications_push -> 013_application_status_history

CREATE TABLE IF NOT EXISTS application_status_events (
               id UUID PRIMARY KEY,
               application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
               actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
               from_status VARCHAR(32) NOT NULL,
               to_status VARCHAR(32) NOT NULL,
               note TEXT,
               by_staff BOOLEAN NOT NULL DEFAULT false,
               created_at TIMESTAMPTZ NOT NULL DEFAULT now()
           );

CREATE INDEX IF NOT EXISTS ix_application_status_events_app_created
               ON application_status_events (application_id, created_at);

UPDATE alembic_version SET version_num='013_application_status_history' WHERE alembic_version.version_num = '012_notifications_push';

DO $$
DECLARE
    r record;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'flatmate_app') THEN
        RETURN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num >= '007') THEN
        RETURN;
    END IF;

    EXECUTE 'GRANT USAGE ON SCHEMA public TO flatmate_app';

    -- Only touch what is missing: ALTER/GRANT take table locks, so a steady-state run
    -- (every deploy) must not lock every table.
    FOR r IN
        SELECT c.relname, c.relrowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend d
              WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e'
          )
    LOOP
        IF NOT r.relrowsecurity THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.relname);
        END IF;
        IF r.relname = 'alembic_version' THEN
            IF has_table_privilege('flatmate_app', format('public.%I', r.relname), 'INSERT, UPDATE, DELETE, TRUNCATE') THEN
                EXECUTE format('REVOKE ALL ON public.%I FROM flatmate_app', r.relname);
            END IF;
            IF NOT has_table_privilege('flatmate_app', format('public.%I', r.relname), 'SELECT') THEN
                EXECUTE format('GRANT SELECT ON public.%I TO flatmate_app', r.relname);
            END IF;
        ELSIF NOT (
            has_table_privilege('flatmate_app', format('public.%I', r.relname), 'SELECT')
            AND has_table_privilege('flatmate_app', format('public.%I', r.relname), 'INSERT')
            AND has_table_privilege('flatmate_app', format('public.%I', r.relname), 'UPDATE')
            AND has_table_privilege('flatmate_app', format('public.%I', r.relname), 'DELETE')
        ) THEN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO flatmate_app', r.relname);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public' AND tablename = r.relname AND policyname = 'flatmate_app_all'
        ) THEN
            EXECUTE format(
                'CREATE POLICY flatmate_app_all ON public.%I FOR ALL TO flatmate_app USING (true) WITH CHECK (true)',
                r.relname
            );
        END IF;
    END LOOP;

    EXECUTE 'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO flatmate_app';

    -- Objects created later by the migrating role get the same grants.
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO flatmate_app';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO flatmate_app';
END $$;;

COMMIT;

