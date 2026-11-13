-- ==============================================================================
-- Seed Data 01: Comprehensive Mock Dataset for Flatmate Platform
-- ==============================================================================

-- Password for all test users is: Password123!
-- Bcrypt hash ($2b$12$e/8lKj0s5wK85w72c6eFjeP7FgnzG1M4oA7M7j5M3jW/8w4L9Kj6W)
-- For portable seed execution, we insert deterministic UUIDs:

-- 1. Insert Users
INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified) VALUES
('11111111-1111-1111-1111-111111111111', 'priya@example.com', '$2b$12$K8M9zBvhwY0b7lR8W3vBde9KjP3l2Z4bJ9fF7q0nC2e4w1lG8s0aW', 'Priya Sharma', 'seeker', true, true),
('22222222-2222-2222-2222-222222222222', 'marcus@example.com', '$2b$12$K8M9zBvhwY0b7lR8W3vBde9KjP3l2Z4bJ9fF7q0nC2e4w1lG8s0aW', 'Marcus Vance', 'seeker', true, true),
('33333333-3333-3333-3333-333333333333', 'liam@example.com', '$2b$12$K8M9zBvhwY0b7lR8W3vBde9KjP3l2Z4bJ9fF7q0nC2e4w1lG8s0aW', 'Liam Chen', 'seeker', true, false),
('44444444-4444-4444-4444-444444444444', 'chloe@example.com', '$2b$12$K8M9zBvhwY0b7lR8W3vBde9KjP3l2Z4bJ9fF7q0nC2e4w1lG8s0aW', 'Chloe Dubois', 'seeker', true, true),
('55555555-5555-5555-5555-555555555555', 'sarah.owner@example.com', '$2b$12$K8M9zBvhwY0b7lR8W3vBde9KjP3l2Z4bJ9fF7q0nC2e4w1lG8s0aW', 'Sarah Jenkins', 'owner', true, true),
('66666666-6666-6666-6666-666666666666', 'david.rentals@example.com', '$2b$12$K8M9zBvhwY0b7lR8W3vBde9KjP3l2Z4bJ9fF7q0nC2e4w1lG8s0aW', 'David Miller', 'owner', true, true),
('77777777-7777-7777-7777-777777777777', 'admin@flatmate.platform', '$2b$12$K8M9zBvhwY0b7lR8W3vBde9KjP3l2Z4bJ9fF7q0nC2e4w1lG8s0aW', 'System Administrator', 'admin', true, true)
ON CONFLICT (id) DO NOTHING;

-- 2. Insert Profiles with 64-dim normalized vector embeddings & lifestyle metadata
INSERT INTO profiles (
    id, user_id, display_name, avatar_url, bio, birth_date, gender, occupation, 
    budget_min, budget_max, move_in_date, lifestyle_vector, lifestyle_traits, preferred_locations
) VALUES
(
    'a1111111-1111-1111-1111-111111111111',
    '11111111-1111-1111-1111-111111111111',
    'Priya S.',
    'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=400',
    'Software engineer working in tech. Early riser, tidy, vegan, loves trail running and weekend farmers markets.',
    '2000-04-12',
    'female',
    'Software Engineer',
    1200, 1800, '2026-12-01',
    array_fill(0.125, ARRAY[64])::vector,
    '{
        "sleep_schedule": "early_bird",
        "cleanliness_level": 5,
        "social_battery": "moderate",
        "work_arrangement": "hybrid",
        "diet": "vegan",
        "smoking": "never",
        "pets": "cats_ok",
        "guests_policy": "occasional_weekends"
    }'::jsonb,
    ARRAY['Downtown', 'Mission District', 'Hayes Valley']
),
(
    'a2222222-2222-2222-2222-222222222222',
    '22222222-2222-2222-2222-222222222222',
    'Marcus V.',
    'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400',
    'Product designer & coffee aficionado. Very respectful of quiet hours, loves cooking dinner parties on Saturdays.',
    '1996-08-20',
    'male',
    'Senior Product Designer',
    1400, 2100, '2026-11-20',
    array_fill(0.120, ARRAY[64])::vector,
    '{
        "sleep_schedule": "early_bird",
        "cleanliness_level": 4,
        "social_battery": "extroverted",
        "work_arrangement": "hybrid",
        "diet": "omnivore",
        "smoking": "never",
        "pets": "loves_pets",
        "guests_policy": "weekends_welcome"
    }'::jsonb,
    ARRAY['Mission District', 'SoMa', 'Potrero Hill']
),
(
    'a3333333-3333-3333-3333-333333333333',
    '33333333-3333-3333-3333-333333333333',
    'Liam C.',
    'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400',
    'PhD student in Neuroscience. Mostly in the lab, quiet study habits, gamer, keeps kitchen spotless.',
    '1998-11-05',
    'male',
    'Neuroscience PhD Student',
    800, 1300, '2026-12-15',
    array_fill(0.095, ARRAY[64])::vector,
    '{
        "sleep_schedule": "night_owl",
        "cleanliness_level": 5,
        "social_battery": "introverted",
        "work_arrangement": "on_site",
        "diet": "vegetarian",
        "smoking": "never",
        "pets": "no_pets",
        "guests_policy": "rarely"
    }'::jsonb,
    ARRAY['Sunset', 'Richmond', 'Cole Valley']
),
(
    'a4444444-4444-4444-4444-444444444444',
    '44444444-4444-4444-4444-444444444444',
    'Chloe D.',
    'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400',
    'Architectural photographer. Passionate about plant-filled spaces, yoga, and acoustic music.',
    '1999-02-14',
    'female',
    'Photographer & Creative',
    1100, 1600, '2026-12-01',
    array_fill(0.118, ARRAY[64])::vector,
    '{
        "sleep_schedule": "early_bird",
        "cleanliness_level": 4,
        "social_battery": "balanced",
        "work_arrangement": "remote",
        "diet": "pescatarian",
        "smoking": "outside_only",
        "pets": "has_small_dog",
        "guests_policy": "occasional_weekends"
    }'::jsonb,
    ARRAY['Hayes Valley', 'Mission District', 'Noe Valley']
)
ON CONFLICT (id) DO NOTHING;

-- 3. Insert Properties (with PostGIS Geometry Points: lng, lat in San Francisco)
INSERT INTO properties (
    id, owner_id, title, description, property_type, location, address, city, state, postal_code,
    monthly_rent, deposit, bills_included, total_bedrooms, total_bathrooms, available_from,
    is_furnished, pets_allowed, smoking_allowed, images
) VALUES
(
    'b1111111-1111-1111-1111-111111111111',
    '55555555-5555-5555-5555-555555555555',
    'Sun-Drenched 3BR Flat in Mission Dolores with Roof Deck',
    'Gorgeous Victorian flat with hardwood floors, chef kitchen, quartz countertops, in-unit washer/dryer and access to a panoramic roof deck. Steps to Mission Dolores Park and BART.',
    'apartment',
    ST_SetSRID(ST_MakePoint(-122.4269, 37.7601), 4326),
    '482 Valencia St',
    'San Francisco',
    'CA',
    '94103',
    4200.00,
    4200.00,
    false,
    3,
    2,
    '2026-12-01',
    true,
    true,
    false,
    ARRAY[
        'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800',
        'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800',
        'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800'
    ]
),
(
    'b2222222-2222-2222-2222-222222222222',
    '66666666-6666-6666-6666-666666666666',
    'Modern Hayes Valley Loft with Private Balcony',
    'Ultra-modern designer loft unit featuring floor-to-ceiling windows, high speed fiber internet, central AC, and secure bike storage. Perfect for young tech professionals or creatives.',
    'condo',
    ST_SetSRID(ST_MakePoint(-122.4243, 37.7758), 4326),
    '315 Octavia St',
    'San Francisco',
    'CA',
    '94102',
    3400.00,
    3400.00,
    true,
    2,
    2,
    '2026-11-25',
    true,
    false,
    false,
    ARRAY[
        'https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800',
        'https://images.unsplash.com/photo-1513694203232-719a280e022f?w=800'
    ]
)
ON CONFLICT (id) DO NOTHING;

-- 4. Insert Specific Rooms
INSERT INTO rooms (
    id, property_id, room_name, room_type, room_rent, deposit, private_bath, is_available, available_from
) VALUES
(
    'c1111111-1111-1111-1111-111111111111',
    'b1111111-1111-1111-1111-111111111111',
    'Master Bedroom with Private En-suite Bath',
    'master_ensuite',
    1550.00,
    1550.00,
    true,
    true,
    '2026-12-01'
),
(
    'c2222222-2222-2222-2222-222222222222',
    'b1111111-1111-1111-1111-111111111111',
    'Sunny Garden View Room',
    'private',
    1325.00,
    1325.00,
    false,
    true,
    '2026-12-01'
)
ON CONFLICT (id) DO NOTHING;

-- 5. Insert Amenities
INSERT INTO property_amenities (property_id, amenity_key) VALUES
('b1111111-1111-1111-1111-111111111111', 'in_unit_laundry'),
('b1111111-1111-1111-1111-111111111111', 'dishwasher'),
('b1111111-1111-1111-1111-111111111111', 'roof_deck'),
('b1111111-1111-1111-1111-111111111111', 'high_speed_wifi'),
('b2222222-2222-2222-2222-222222222222', 'central_ac'),
('b2222222-2222-2222-2222-222222222222', 'elevator'),
('b2222222-2222-2222-2222-222222222222', 'bike_storage')
ON CONFLICT DO NOTHING;

-- 6. Insert Flatmate Hunting Group
INSERT INTO groups (id, creator_id, name, description, target_budget_total, target_city, target_move_in) VALUES
(
    'd1111111-1111-1111-1111-111111111111',
    '11111111-1111-1111-1111-111111111111',
    'Mission / Hayes Valley Co-Living Trio',
    'Teaming up to lease a 3-bedroom apartment with great natural light and shared work-from-home friendly vibes.',
    4200,
    'San Francisco',
    '2026-12-01'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO group_members (group_id, user_id, role) VALUES
('d1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'leader'),
('d1111111-1111-1111-1111-111111111111', '44444444-4444-4444-4444-444444444444', 'member')
ON CONFLICT DO NOTHING;

-- 7. Insert Applications
INSERT INTO applications (
    id, applicant_id, property_id, room_id, status, introduction, proposed_rent, move_in_target
) VALUES
(
    'e1111111-1111-1111-1111-111111111111',
    '11111111-1111-1111-1111-111111111111',
    'b1111111-1111-1111-1111-111111111111',
    'c1111111-1111-1111-1111-111111111111',
    'submitted',
    'Hi Sarah! I am a full-time software engineer at Stripe. I fell in love with your Mission Dolores flat and would be thrilled to take the Master ensuite room.',
    1550.00,
    '2026-12-01'
)
ON CONFLICT (id) DO NOTHING;
