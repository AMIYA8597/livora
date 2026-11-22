#!/usr/bin/env bash
# Apply the Alembic schema, then load idempotent development seed data.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/apps/api"
echo "Applying migrations (alembic upgrade head)..."
python -m alembic upgrade head
echo "Seeding development data..."
python "$ROOT/database/seeds/seed.py" "$@"
