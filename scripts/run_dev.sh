#!/usr/bin/env bash
set -e

echo "🚀 Starting Flatmate Platform (All Services)..."

# Ensure docker containers are up
docker compose up -d postgres redis minio

# Run turbo dev
pnpm dev
