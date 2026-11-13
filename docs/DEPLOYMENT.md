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
| `SUPABASE_ANON_KEY` | Staging / Prod | Supabase public anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Staging / Prod | Secure backend service key (strictly server-side) |
| `SUPABASE_JWT_SECRET` | Staging / Prod | JWT verification secret for Supabase Auth tokens |
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
