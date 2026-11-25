# Production Deployment & Infrastructure Runbook

**Target Architecture:** Free-First, Provider-Independent Modular Monolith  
**Primary Database:** Supabase PostgreSQL (or self-hosted PostgreSQL 16 with PostGIS & pgvector)  
**Containerization:** Multi-stage Docker + Docker Compose  

---

## 1. Environment Configurations

| Variable | Environment | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production`, `staging`, `development` | Runtime environment flag |
| `DATABASE_URL` | All | `postgresql+asyncpg://...` primary database connection string |
| `DATABASE_SYNC_URL` | All | `postgresql://...` sync connection string used by Alembic |
| `SUPABASE_URL` | Staging / Prod | Managed Supabase API URL |
| `SUPABASE_SECRET_KEY` | Staging / Prod | Secret key `sb_secret_...` for Storage (strictly server-side). The legacy service-role, anon and JWT-secret values are not used. |
| `REDIS_URL` | All | Redis cache and Pub/Sub connection string |

---

## 2. Zero-Downtime Migration Execution Procedure

```bash
# Step 1: Pre-deployment migration dry run in staging
cd apps/api
alembic check

# Step 2: Apply forward migrations
alembic upgrade head

# Step 3: Verify migration status
alembic current
```

---

## 3. Docker Production Deployment

```bash
# Build production images
docker compose -f docker-compose.prod.yml build

# Start services in detached mode
docker compose -f docker-compose.prod.yml up -d

# Verify container health checks
docker compose -f docker-compose.prod.yml ps
```
