#!/usr/bin/env bash
set -e

echo "🚀 Setting up Flatmate Platform Development Environment..."

# 1. Check .env
if [ ! -f .env ]; then
  echo "📄 Creating .env from .env.example..."
  cp .env.example .env
fi

# 2. Node Dependencies
echo "📦 Installing Node dependencies via pnpm..."
pnpm install

# 3. Python Virtualenv
echo "🐍 Setting up Python virtual environment..."
cd apps/api
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
cd ../..

echo "🐳 Starting local database and cache containers..."
docker compose up -d postgres redis minio

echo "🌱 Waiting for database to be ready..."
sleep 4

echo "🌱 Running migrations and seeds..."
./scripts/seed_db.sh

echo "🎉 Setup complete! Run 'pnpm dev' to start local development."
