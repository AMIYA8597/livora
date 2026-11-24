# Staging & Production Deployment Guide
## Flatmate Compatibility & Rental Marketplace

**Phase:** Phase 23 — Real Hosted Database Integration, Complete Full-Stack Validation, AI/ML Audit & Security Release Gate  
**Target Architecture:** FastAPI (Backend) + Next.js 14 (Frontend) + Hosted Supabase / PostgreSQL (PostGIS + pgvector)  
**Database Schema:** 42 Domain Tables + `alembic_version` (43 Tables total)  
**Migration Head:** `002_messaging_realtime`  
**Containerization:** Multi-stage Non-Root Docker (`infrastructure/docker/Dockerfile.api`, `infrastructure/docker/Dockerfile.web`)  
**Status:** **`CONDITIONALLY READY`** (Full-Stack Verified; Awaiting Hosted Migration Apply Approval)  

---

## 1. Environment Configurations & Secrets Inventory

The platform reads configuration from environment variables. Example templates with non-secret placeholders:
- [`.env.example`](file:///D:/work/flatmate/.env.example) (Local development)
- [`.env.staging.example`](file:///D:/work/flatmate/.env.staging.example) (Isolated staging environment)
- [`.env.staging.local.example`](file:///D:/work/flatmate/.env.staging.local.example) (Local staging drill)
- [`.env.production.example`](file:///D:/work/flatmate/.env.production.example) (Hardened production deployment)

### 1.1 Variable Master Table

| Variable | Target Environment | Scope | Required | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | All | Backend | **YES** | `development`, `staging`, or `production` |
| `SECRET_KEY` | All | Backend | **YES** | Internal cryptographic token (Min 32 characters) |
| `DATABASE_URL` | All | Backend | **YES** | Async PostgreSQL connection URI (`postgresql+asyncpg://...`) |
| `DATABASE_SYNC_URL` | All | Backend | **YES** | Sync PostgreSQL connection URI for Alembic migrations |
| `SUPABASE_URL` | Staging / Prod | All | **YES** | Hosted Supabase project URL (`https://<ref>.supabase.co`) |
| `SUPABASE_ANON_KEY` | Staging / Prod | All | **YES** | Public anon JWT key (Safe for client bundle) |
| `SUPABASE_SERVICE_ROLE_KEY` | Staging / Prod | Backend ONLY | **YES** | Admin service-role key (**NEVER leak to browser**) |
| `SUPABASE_JWT_SECRET` | Staging / Prod | Backend ONLY | **YES** | Supabase Auth JWT verification secret |
| `STORAGE_TYPE` | All | Backend | **YES** | `supabase`, `local`, or `s3` |
| `SUPABASE_STORAGE_BUCKET`| All | Backend | **YES** | Default media bucket (`flatmate-media-staging`) |
| `CORS_ORIGINS` | All | Backend | **YES** | Allowed browser origins JSON array |
| `NEXT_PUBLIC_APP_URL` | All | Frontend | **YES** | Web application base URL |
| `NEXT_PUBLIC_API_URL` | All | Frontend | **YES** | Centralized API client base URL (ends in `/api/v1`) |
| `NEXT_PUBLIC_WS_URL` | All | Frontend | **YES** | Real-time WebSocket base URL |

---

## 2. Zero-Leak Validation & Diagnostics

Before launching, validate environment format without displaying secrets:
```bash
# Validate staging environment configuration
python scripts/validate_environment_config.py .env.staging
```

Probe live connectivity to Supabase Auth, PostgreSQL, and Storage:
```bash
python scripts/test_supabase_connectivity.py
```

---

## 3. Step-by-Step Hosted Supabase Deployment Runbook

### Step 1: Provision Hosted Supabase Extensions
In the Supabase SQL Editor, enable required PostgreSQL extensions:
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "vector";
```

### Step 2: Apply Database Migrations
Run Alembic against the hosted database:
```bash
alembic upgrade head
```
Verify current head revision:
```bash
alembic current
# Expected: 002_messaging_realtime (head)
```

### Step 3: Apply Row-Level Security (RLS) Policies
In the Supabase SQL Editor or via database connection:
```bash
psql -d "$DATABASE_SYNC_URL" -f database/policies/rls_policies.sql
```

### Step 4: Create Supabase Storage Buckets
In Supabase Dashboard (`Storage -> New Bucket`):
1. `staging-property-photos` (Public visibility, authenticated uploads)
2. `staging-verification-docs` (Private visibility, presigned URL access only)
3. `flatmate-media-staging` (General application media)

### Step 5: Managed Redis and the Background Worker
The API works without Redis, but then rate limits are per instance, chat doesn't reach people
connected to another instance, and the worker can't run. The worker handles three jobs:
- retrying failed emails (every 15 seconds)
- hourly maintenance, including erasing accounts whose 30-day deletion grace has passed
- the weekly ranker retrain

1. **Create a Redis.** Upstash or Redis Cloud reach Cloud Run over the internet with TLS and
   need nothing else. Memorystore needs Direct VPC egress: set the GitHub `staging` environment
   variables `STAGING_VPC_NETWORK` and `STAGING_VPC_SUBNET`.
2. **Store its URL** (`rediss://...` for TLS) as the Secret Manager secret `STAGING_REDIS_URL`
   in the GCP project, and give the Cloud Run runtime service account the Secret Accessor role
   on it:
   ```bash
   printf '%s' "$REDIS_URL" | gcloud secrets create STAGING_REDIS_URL --data-file=-
   ```
3. **Run the Staging Deployment workflow again.** It passes the URL to the API and deploys
   `flatmate-worker-staging`:
   - the same image, running `python -m app.workers.run`
   - one instance, with CPU always on
   - beat runs inside the worker, so there is exactly one scheduler

   The deploy succeeds only once the worker has reached Redis and is taking tasks. Until the
   secret exists, the workflow warns and skips the worker.
4. **Check it:**
   - `gcloud run services logs read flatmate-worker-staging --region asia-south1` shows
     `celery@... ready` and `outbox.dispatch` running every 15 seconds.
   - The API's `/health/ready` reports `"redis": {"status": "ok"}`.

### Step 6: Verify Live End-to-End User Journeys
Execute the automated live integration suite:
```bash
python scripts/e2e_live_staging_workflows.py
```

---

## 4. Local Staging Reference Verification

The platform has been empirically verified on local reference staging:
- Frontend: `http://localhost:3001` (32 routes compiled, 31 automated tests passing)
- Backend: `http://localhost:8001` (110 routes registered, 136 automated tests passing)
- PostgreSQL: `localhost:5432/flatmate_staging_disposable` (43 tables present, 0 schema drift)
- Security & Privacy: 100% boundary enforcement (BOLA, DPDP address masking, coordinate fuzzing)
