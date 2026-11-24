"""Lifestyle answers in one vocabulary, and copied to the profile that matching reads.

Matching, the flatmate filters, the ranker, embeddings and smart replies read
`profiles.lifestyle_traits`, but the 10-dimension form saved only to `lifestyle_profiles`, and
the older quiz stored other keys and values (`diet: vegetarian`, `pets: has_cat`,
`smoking: allowed`). This migration:

1. converts old values in `lifestyle_profiles` (omnivore -> non_veg, balcony_only -> outside_only, ...);
2. renames the quiz keys in `profiles.lifestyle_traits` (diet -> diet_preference, pets ->
   pet_preference; a form key already present wins) and converts their values;
3. copies each saved form onto the profile (the form's answers win);
4. recomputes `profiles.lifestyle_vector` for every profile with answers (the embedding trigger
   from 003 follows) and queues an embedding refresh for each.

Plain SQL, so `alembic upgrade --sql` (the hosted schema file) carries it too. The maps and the
vector formula are frozen copies of app/modules/lifestyle/traits.py as of this revision.

Downgrade leaves the data converted: the old values can't be recovered and the app no longer
reads them.

Revision ID: 015_canonical_lifestyle_traits
Revises: 014_account_deletion
"""
from typing import Dict, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_canonical_lifestyle_traits"
down_revision: Union[str, None] = "014_account_deletion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIM = 64

RENAMED = {"diet": "diet_preference", "pets": "pet_preference"}
LEGACY_VALUES: Dict[str, Dict[str, str]] = {
    "diet_preference": {
        "vegetarian": "pure_veg", "veg_and_egg": "eggetarian", "omnivore": "non_veg",
        "pescatarian": "non_veg", "halal": "non_veg", "kosher": "non_veg",
    },
    "pet_preference": {"has_cat": "loves_pets", "has_dog": "loves_pets"},
    "smoking": {"allowed": "permitted", "regular": "permitted", "balcony_only": "outside_only"},
    "social_battery": {"moderate": "balanced"},
    "work_arrangement": {"office": "on_site"},
}
FORM_FIELDS = (
    "sleep_schedule", "work_arrangement", "cleanliness_level", "chore_philosophy", "noise_tolerance",
    "instrument_or_music", "lighting_preference", "guests_policy", "social_battery", "diet_preference",
    "non_veg_cooking_allowed", "cooks_at_home", "smoking", "drinking", "pet_preference",
)

# Vector slices: (start, end, trait, value map, default, wave). Waves: cos(i), sin(i), cos(i/2).
SLEEP = {"early_bird": 1.0, "flexible": 0.5, "rotational": 0.3, "night_owl": 0.0}
SOCIAL = {"introverted": 0.2, "balanced": 0.7, "extroverted": 1.0}
WORK = {"remote": 0.1, "hybrid": 0.5, "on_site": 0.9, "shift_work": 0.7}
DIET = {"vegan": 1.0, "jain": 0.9, "pure_veg": 0.8, "eggetarian": 0.65, "non_veg": 0.4}
SMOKING = {"never": 0.0, "outside_only": 0.5, "permitted": 1.0}
PETS = {"no_pets": 0.0, "allergic": 0.0, "cats_ok": 0.4, "dogs_ok": 0.6, "cats_and_dogs_ok": 0.8, "loves_pets": 1.0}


def _lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _case(expr: str, mapping: Dict[str, object], default: str) -> str:
    whens = " ".join(f"WHEN {_lit(k)} THEN {v if not isinstance(v, str) else _lit(v)}" for k, v in mapping.items())
    return f"(CASE {expr} {whens} ELSE {default} END)"


def _vector_sql(traits: str) -> str:
    clean = (
        f"(CASE WHEN {traits} ? 'cleanliness_level' THEN "
        f"(CASE WHEN ({traits}->>'cleanliness_level') ~ '^-?[0-9]+(\\.[0-9]+)?$' "
        f"THEN ({traits}->>'cleanliness_level')::float8 / 5.0 ELSE 0.6 END) ELSE 0.6 END)"
    )

    def val(key: str, mapping: Dict[str, float], default: float) -> str:
        return _case(f"({traits}->>'{key}')", mapping, str(default))

    raw = f"""
        CASE
            WHEN i < 8  THEN {val('sleep_schedule', SLEEP, 0.5)} * cos(i)
            WHEN i < 16 THEN {clean} * sin(i)
            WHEN i < 24 THEN {val('social_battery', SOCIAL, 0.5)} * cos(i)
            WHEN i < 32 THEN {val('work_arrangement', WORK, 0.5)} * sin(i)
            WHEN i < 40 THEN {val('diet_preference', DIET, 0.5)} * cos(i)
            WHEN i < 48 THEN {val('smoking', SMOKING, 0.0)} * sin(i)
            ELSE {val('pet_preference', PETS, 0.5)} * cos(i * 0.5)
        END"""
    # L2-normalised; an all-zero vector stays as it is (like the Python version).
    return f"""(
        SELECT CASE WHEN n > 0 THEN array_agg(x / n ORDER BY i) ELSE array_agg(x ORDER BY i) END
          FROM (SELECT i, x, sqrt(sum(x * x) OVER ()) AS n
                  FROM (SELECT i, ({raw})::float8 AS x FROM generate_series(0, {DIM - 1}) AS i) raw) v
         GROUP BY n
    )"""


def upgrade() -> None:
    # 1. Old values in the saved forms.
    for column, mapping in LEGACY_VALUES.items():
        op.execute(sa.text(
            f"UPDATE lifestyle_profiles SET {column} = {_case(column, mapping, column)} "
            f"WHERE {column} IN ({', '.join(_lit(k) for k in mapping)})"
        ))

    # 2. Quiz keys -> form keys on the profile (a form key already there wins), then old values.
    for old, new in RENAMED.items():
        op.execute(sa.text(f"""
            UPDATE profiles
               SET lifestyle_traits = (lifestyle_traits - '{old}')
                   || CASE WHEN lifestyle_traits ? '{new}' THEN '{{}}'::jsonb
                           ELSE jsonb_build_object('{new}', lifestyle_traits->'{old}') END
             WHERE lifestyle_traits ? '{old}'
        """))
    for key, mapping in LEGACY_VALUES.items():
        op.execute(sa.text(f"""
            UPDATE profiles
               SET lifestyle_traits = jsonb_set(lifestyle_traits, '{{{key}}}',
                   to_jsonb({_case(f"(lifestyle_traits->>'{key}')", mapping, "NULL")}::text))
             WHERE lifestyle_traits->>'{key}' IN ({', '.join(_lit(k) for k in mapping)})
        """))

    # 3. The saved form onto the profile; its answers win.
    fields = ", ".join(f"'{f}', lp.{f}" for f in FORM_FIELDS)
    op.execute(sa.text(f"""
        UPDATE profiles p
           SET lifestyle_traits = COALESCE(p.lifestyle_traits, '{{}}'::jsonb)
                                  || jsonb_strip_nulls(jsonb_build_object({fields}))
          FROM lifestyle_profiles lp
         WHERE lp.user_id = p.user_id
    """))

    # 4. The matching vector for every profile with answers, and a semantic re-embed.
    op.execute(sa.text(f"""
        UPDATE profiles
           SET lifestyle_vector = {_vector_sql('lifestyle_traits')}
         WHERE lifestyle_traits IS NOT NULL AND lifestyle_traits <> '{{}}'::jsonb
    """))
    op.execute(sa.text("""
        INSERT INTO outbox_events (id, event_type, payload, status, retry_count, created_at, next_attempt_at)
        SELECT gen_random_uuid(), 'embedding.refresh',
               jsonb_build_object('entity_type', 'profile', 'entity_id', user_id::text),
               'pending', 0, now(), now()
          FROM profiles
         WHERE lifestyle_traits IS NOT NULL AND lifestyle_traits <> '{}'::jsonb
    """))


def downgrade() -> None:
    # Data-only revision; see the module docstring.
    pass
