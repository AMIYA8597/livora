"""Every Indian state and union territory, with its capital, as the list of cities listings use.

The countries/states/cities tables existed but held only development seed rows, and the web
offered six hardcoded cities. This migration:

1. adds `states.kind` (state or union_territory) and `states.capital_city_id`;
2. adds `cities.aliases` (other names people search for, like Bangalore or Port Blair) and
   `cities.is_active` (open for new listings);
3. upserts India, its 28 states and 8 union territories (two-letter codes as used on vehicle
   registrations: KA, MH, TS, ...), each capital, and Pune; existing rows are matched by state
   code and city slug, so development seeds are updated, not duplicated;
4. makes (country_id, code) unique for states;
5. renames listings whose city is an alias (Bangalore, Delhi NCR, ...) to the official name.

Plain SQL, so `alembic upgrade --sql` (the hosted schema file) carries it too. Coordinates are
city centres. Where a state has two capitals (Jammu and Kashmir), the first listed is used and
both cities are included. Chandigarh is the capital of Punjab, Haryana and the union territory.

Downgrade drops the new columns and constraint; the rows stay.

Revision ID: 016_india_locations
Revises: 015_canonical_lifestyle_traits
"""
from typing import List, Sequence, Tuple, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016_india_locations"
down_revision: Union[str, None] = "015_canonical_lifestyle_traits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# code, name, kind, capital slug
STATES: List[Tuple[str, str, str, str]] = [
    ("AP", "Andhra Pradesh", "state", "amaravati"),
    ("AR", "Arunachal Pradesh", "state", "itanagar"),
    ("AS", "Assam", "state", "dispur"),
    ("BR", "Bihar", "state", "patna"),
    ("CG", "Chhattisgarh", "state", "raipur"),
    ("GA", "Goa", "state", "panaji"),
    ("GJ", "Gujarat", "state", "gandhinagar"),
    ("HR", "Haryana", "state", "chandigarh"),
    ("HP", "Himachal Pradesh", "state", "shimla"),
    ("JH", "Jharkhand", "state", "ranchi"),
    ("KA", "Karnataka", "state", "bengaluru"),
    ("KL", "Kerala", "state", "thiruvananthapuram"),
    ("MP", "Madhya Pradesh", "state", "bhopal"),
    ("MH", "Maharashtra", "state", "mumbai"),
    ("MN", "Manipur", "state", "imphal"),
    ("ML", "Meghalaya", "state", "shillong"),
    ("MZ", "Mizoram", "state", "aizawl"),
    ("NL", "Nagaland", "state", "kohima"),
    ("OD", "Odisha", "state", "bhubaneswar"),
    ("PB", "Punjab", "state", "chandigarh"),
    ("RJ", "Rajasthan", "state", "jaipur"),
    ("SK", "Sikkim", "state", "gangtok"),
    ("TN", "Tamil Nadu", "state", "chennai"),
    ("TS", "Telangana", "state", "hyderabad"),
    ("TR", "Tripura", "state", "agartala"),
    ("UP", "Uttar Pradesh", "state", "lucknow"),
    ("UK", "Uttarakhand", "state", "dehradun"),
    ("WB", "West Bengal", "state", "kolkata"),
    ("AN", "Andaman and Nicobar Islands", "union_territory", "sri-vijaya-puram"),
    ("CH", "Chandigarh", "union_territory", "chandigarh"),
    ("DD", "Dadra and Nagar Haveli and Daman and Diu", "union_territory", "daman"),
    ("DL", "Delhi", "union_territory", "new-delhi"),
    ("JK", "Jammu and Kashmir", "union_territory", "srinagar"),
    ("LA", "Ladakh", "union_territory", "leh"),
    ("LD", "Lakshadweep", "union_territory", "kavaratti"),
    ("PY", "Puducherry", "union_territory", "puducherry"),
]

# slug, name, state code, tier, latitude, longitude, aliases
CITIES: List[Tuple[str, str, str, int, float, float, Tuple[str, ...]]] = [
    ("amaravati", "Amaravati", "AP", 2, 16.5150, 80.5150, ()),
    ("itanagar", "Itanagar", "AR", 2, 27.0844, 93.6053, ()),
    ("dispur", "Dispur", "AS", 2, 26.1433, 91.7898, ("Guwahati",)),
    ("patna", "Patna", "BR", 2, 25.5941, 85.1376, ()),
    ("raipur", "Raipur", "CG", 2, 21.2514, 81.6296, ("Nava Raipur",)),
    ("panaji", "Panaji", "GA", 2, 15.4909, 73.8278, ("Panjim",)),
    ("gandhinagar", "Gandhinagar", "GJ", 2, 23.2156, 72.6369, ()),
    ("shimla", "Shimla", "HP", 2, 31.1048, 77.1734, ("Simla",)),
    ("ranchi", "Ranchi", "JH", 2, 23.3441, 85.3096, ()),
    ("bengaluru", "Bengaluru", "KA", 1, 12.9716, 77.5946, ("Bangalore",)),
    ("thiruvananthapuram", "Thiruvananthapuram", "KL", 2, 8.5241, 76.9366, ("Trivandrum",)),
    ("bhopal", "Bhopal", "MP", 2, 23.2599, 77.4126, ()),
    ("mumbai", "Mumbai", "MH", 1, 19.0760, 72.8777, ("Bombay",)),
    ("pune", "Pune", "MH", 1, 18.5204, 73.8567, ("Poona",)),
    ("imphal", "Imphal", "MN", 2, 24.8170, 93.9368, ()),
    ("shillong", "Shillong", "ML", 2, 25.5788, 91.8933, ()),
    ("aizawl", "Aizawl", "MZ", 2, 23.7271, 92.7176, ()),
    ("kohima", "Kohima", "NL", 2, 25.6751, 94.1086, ()),
    ("bhubaneswar", "Bhubaneswar", "OD", 2, 20.2961, 85.8245, ()),
    ("jaipur", "Jaipur", "RJ", 2, 26.9124, 75.7873, ()),
    ("gangtok", "Gangtok", "SK", 2, 27.3389, 88.6065, ()),
    ("chennai", "Chennai", "TN", 1, 13.0827, 80.2707, ("Madras",)),
    ("hyderabad", "Hyderabad", "TS", 1, 17.3850, 78.4867, ("Secunderabad",)),
    ("agartala", "Agartala", "TR", 2, 23.8315, 91.2868, ()),
    ("lucknow", "Lucknow", "UP", 2, 26.8467, 80.9462, ()),
    ("dehradun", "Dehradun", "UK", 2, 30.3165, 78.0322, ()),
    ("kolkata", "Kolkata", "WB", 1, 22.5726, 88.3639, ("Calcutta",)),
    ("sri-vijaya-puram", "Sri Vijaya Puram", "AN", 2, 11.6234, 92.7265, ("Port Blair",)),
    ("chandigarh", "Chandigarh", "CH", 2, 30.7333, 76.7794, ()),
    ("daman", "Daman", "DD", 2, 20.3974, 72.8328, ()),
    ("new-delhi", "New Delhi", "DL", 1, 28.6139, 77.2090, ("Delhi", "Delhi NCR")),
    ("srinagar", "Srinagar", "JK", 2, 34.0837, 74.7973, ()),
    ("jammu", "Jammu", "JK", 2, 32.7266, 74.8570, ()),
    ("leh", "Leh", "LA", 2, 34.1526, 77.5771, ()),
    ("kavaratti", "Kavaratti", "LD", 2, 10.5669, 72.6420, ()),
    ("puducherry", "Puducherry", "PY", 2, 11.9416, 79.8083, ("Pondicherry",)),
]


def _lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _array(values: Tuple[str, ...]) -> str:
    return "ARRAY[" + ", ".join(_lit(v) for v in values) + "]::varchar[]" if values else "'{}'::varchar[]"


def upgrade() -> None:
    # One statement per call: asyncpg runs a single command per prepared statement.
    for statement in (
        "ALTER TABLE states ADD COLUMN IF NOT EXISTS kind varchar(16) NOT NULL DEFAULT 'state'",
        "ALTER TABLE states ADD COLUMN IF NOT EXISTS capital_city_id uuid REFERENCES cities(id) ON DELETE SET NULL",
        "ALTER TABLE cities ADD COLUMN IF NOT EXISTS aliases varchar(100)[] NOT NULL DEFAULT '{}'",
        "ALTER TABLE cities ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true",
        """DO $$ BEGIN
            ALTER TABLE states ADD CONSTRAINT chk_states_kind CHECK (kind IN ('state', 'union_territory'));
        EXCEPTION WHEN duplicate_object THEN NULL; END $$""",
    ):
        op.execute(sa.text(statement))

    op.execute(sa.text("""
        INSERT INTO countries (id, code, name, currency_code, phone_code)
        VALUES (gen_random_uuid(), 'IND', 'India', 'INR', '+91')
        ON CONFLICT (code) DO NOTHING
    """))

    state_rows = ",\n".join(f"({_lit(c)}, {_lit(n)}, {_lit(k)})" for c, n, k, _ in STATES)
    op.execute(sa.text(f"""
        WITH data(code, name, kind) AS (VALUES {state_rows}),
        india AS (SELECT id FROM countries WHERE code = 'IND'),
        updated AS (
            UPDATE states s SET name = d.name, kind = d.kind
              FROM data d, india
             WHERE s.country_id = india.id AND s.code = d.code
         RETURNING s.code
        )
        INSERT INTO states (id, country_id, code, name, kind)
        SELECT gen_random_uuid(), india.id, d.code, d.name, d.kind
          FROM data d, india
         WHERE d.code NOT IN (SELECT code FROM updated)
           AND NOT EXISTS (SELECT 1 FROM states s WHERE s.country_id = india.id AND s.code = d.code)
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE states ADD CONSTRAINT uq_states_country_code UNIQUE (country_id, code);
        EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;
    """))

    city_rows = ",\n".join(
        f"({_lit(slug)}, {_lit(name)}, {_lit(st)}, {tier}, {lat}, {lng}, {_array(aliases)})"
        for slug, name, st, tier, lat, lng, aliases in CITIES
    )
    op.execute(sa.text(f"""
        WITH data(slug, name, state_code, tier, lat, lng, aliases) AS (VALUES {city_rows})
        INSERT INTO cities (id, state_id, slug, name, tier, center_location, aliases, is_active)
        SELECT gen_random_uuid(), s.id, d.slug, d.name, d.tier,
               ST_SetSRID(ST_MakePoint(d.lng, d.lat), 4326), d.aliases, true
          FROM data d
          JOIN states s ON s.code = d.state_code
          JOIN countries c ON c.id = s.country_id AND c.code = 'IND'
        ON CONFLICT (slug) DO UPDATE
           SET name = EXCLUDED.name, state_id = EXCLUDED.state_id, tier = EXCLUDED.tier,
               center_location = EXCLUDED.center_location, aliases = EXCLUDED.aliases
    """))

    capital_rows = ",\n".join(f"({_lit(code)}, {_lit(slug)})" for code, _, _, slug in STATES)
    op.execute(sa.text(f"""
        WITH data(code, slug) AS (VALUES {capital_rows})
        UPDATE states s SET capital_city_id = ci.id
          FROM data d, cities ci, countries c
         WHERE s.code = d.code AND ci.slug = d.slug AND c.id = s.country_id AND c.code = 'IND'
    """))

    # Listings saved under another name for a catalogue city use the official one.
    op.execute(sa.text("""
        UPDATE properties p SET city = ci.name, state = COALESCE(NULLIF(p.state, ''), s.name)
          FROM cities ci JOIN states s ON s.id = ci.state_id
         WHERE p.city <> ci.name
           AND lower(btrim(p.city)) IN (SELECT lower(a) FROM unnest(ci.aliases) a UNION SELECT lower(ci.name))
    """))


def downgrade() -> None:
    for statement in (
        "ALTER TABLE states DROP CONSTRAINT IF EXISTS uq_states_country_code",
        "ALTER TABLE states DROP CONSTRAINT IF EXISTS chk_states_kind",
        "ALTER TABLE states DROP COLUMN IF EXISTS capital_city_id",
        "ALTER TABLE states DROP COLUMN IF EXISTS kind",
        "ALTER TABLE cities DROP COLUMN IF EXISTS aliases",
        "ALTER TABLE cities DROP COLUMN IF EXISTS is_active",
    ):
        op.execute(sa.text(statement))
