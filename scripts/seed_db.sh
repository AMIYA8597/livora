#!/usr/bin/env bash
set -e

echo "🌱 Running Flatmate Platform Database Migrations & Seeds..."

if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Execute seed.py script inside apps/api virtualenv or directly via python
cd database/seeds
python3 seed.py
cd ../..

echo "✅ Database seeded successfully."
