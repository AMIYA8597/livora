"""Billing: Razorpay subscriptions, payments, webhook events, featured listings and the two plans.

Revision ID: 010_billing
Revises: 009_ml_platform

- `subscription_plans`: audience, Razorpay period/interval and the Razorpay plan id (created
  lazily at first checkout, and again whenever the price changes). Seeds "seeker_pro" and
  "owner_pro" at placeholder prices; change `price_inr` to reprice.
- `subscriptions`: provider subscription id (unique), Razorpay status, paid period
  (`expires_at` may be null until the first charge), cancel-at-period-end, and the timestamp of
  the newest provider event applied. At most one open subscription per user and plan.
- `payments`: one row per provider payment (unique payment id), with method and failure reason.
- `billing_events`: every verified webhook delivery, unique by provider event id.
- `properties.featured_until`: featured listings are shown first until this time.

Every statement is idempotent because migration 001 creates tables from the current models.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_billing"
down_revision: Union[str, None] = "009_ml_platform"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OPEN_STATUSES = "('created', 'authenticated', 'active', 'pending')"


def upgrade() -> None:
    plans = [
        "ADD COLUMN IF NOT EXISTS audience VARCHAR(16) NOT NULL DEFAULT 'seeker'",
        "ADD COLUMN IF NOT EXISTS description TEXT",
        "ADD COLUMN IF NOT EXISTS period VARCHAR(16) NOT NULL DEFAULT 'monthly'",
        "ADD COLUMN IF NOT EXISTS interval INTEGER NOT NULL DEFAULT 1",
        "ADD COLUMN IF NOT EXISTS razorpay_plan_id VARCHAR(64)",
        "ADD COLUMN IF NOT EXISTS razorpay_plan_amount INTEGER",
        "ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0",
    ]
    for clause in plans:
        op.execute(f"ALTER TABLE subscription_plans {clause}")

    subs = [
        "ADD COLUMN IF NOT EXISTS provider VARCHAR(16) NOT NULL DEFAULT 'razorpay'",
        "ADD COLUMN IF NOT EXISTS provider_subscription_id VARCHAR(64)",
        "ADD COLUMN IF NOT EXISTS short_url VARCHAR(255)",
        "ADD COLUMN IF NOT EXISTS current_start TIMESTAMPTZ",
        "ADD COLUMN IF NOT EXISTS cancel_at_period_end BOOLEAN NOT NULL DEFAULT false",
        "ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ",
        "ADD COLUMN IF NOT EXISTS provider_event_at BIGINT",
        "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        "ALTER COLUMN expires_at DROP NOT NULL",
        "ALTER COLUMN status SET DEFAULT 'created'",
    ]
    for clause in subs:
        op.execute(f"ALTER TABLE subscriptions {clause}")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS subscriptions_provider_subscription_id_key "
        "ON subscriptions (provider_subscription_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_one_open_per_plan "
        f"ON subscriptions (user_id, plan_id) WHERE status IN {OPEN_STATUSES}"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_subscriptions_user_expires ON subscriptions (user_id, expires_at)")

    pays = [
        "ADD COLUMN IF NOT EXISTS provider VARCHAR(16) NOT NULL DEFAULT 'razorpay'",
        "ADD COLUMN IF NOT EXISTS method VARCHAR(32)",
        "ADD COLUMN IF NOT EXISTS gateway_invoice_id VARCHAR(100)",
        "ADD COLUMN IF NOT EXISTS failure_reason VARCHAR(255)",
        "ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ",
    ]
    for clause in pays:
        op.execute(f"ALTER TABLE payments {clause}")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS payments_gateway_payment_id_key ON payments (gateway_payment_id)"
    )

    op.execute(sa.text("""
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
        )
    """))

    op.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS featured_until TIMESTAMPTZ")
    op.execute("CREATE INDEX IF NOT EXISTS ix_properties_featured_until ON properties (featured_until)")

    op.execute(sa.text("""
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
        ON CONFLICT (code) DO NOTHING
    """))


def downgrade() -> None:
    op.execute("DELETE FROM subscription_plans WHERE code IN ('seeker_pro', 'owner_pro') "
               "AND NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.plan_id = subscription_plans.id)")
    op.execute("DROP INDEX IF EXISTS ix_properties_featured_until")
    op.execute("ALTER TABLE properties DROP COLUMN IF EXISTS featured_until")
    op.execute("DROP TABLE IF EXISTS billing_events")
    # On databases built by 001 (create_all) these are constraints, elsewhere plain indexes.
    op.execute("ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_gateway_payment_id_key")
    op.execute("DROP INDEX IF EXISTS payments_gateway_payment_id_key")
    for col in ("paid_at", "failure_reason", "gateway_invoice_id", "method", "provider"):
        op.execute(f"ALTER TABLE payments DROP COLUMN IF EXISTS {col}")
    op.execute("DROP INDEX IF EXISTS ix_subscriptions_user_expires")
    op.execute("DROP INDEX IF EXISTS uq_subscriptions_one_open_per_plan")
    op.execute("ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS subscriptions_provider_subscription_id_key")
    op.execute("DROP INDEX IF EXISTS subscriptions_provider_subscription_id_key")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN status SET DEFAULT 'active'")
    for col in ("updated_at", "provider_event_at", "cancelled_at", "cancel_at_period_end",
                "current_start", "short_url", "provider_subscription_id", "provider"):
        op.execute(f"ALTER TABLE subscriptions DROP COLUMN IF EXISTS {col}")
    for col in ("sort_order", "razorpay_plan_amount", "razorpay_plan_id", "interval", "period",
                "description", "audience"):
        op.execute(f"ALTER TABLE subscription_plans DROP COLUMN IF EXISTS {col}")
