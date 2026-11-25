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
| `SUPABASE_SECRET_KEY` | Staging / Prod | Backend ONLY | **YES** | Secret key `sb_secret_...` (Project Settings > API Keys) for Storage. **Never in the browser.** The legacy `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY` and `SUPABASE_JWT_SECRET` are not used: turn the legacy keys off in the dashboard. |
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

## 4. Production

Production runs exactly what staging built and checked. A release goes: verified backup →
migrations → API → worker → web app, all from one run of the **Production Deployment** workflow.

### 4.1 One-time setup

**Google Cloud** (the same project as staging, or set `RELEASE_IMAGE_REPOSITORY`; see below):
1. Create the Secret Manager secrets the services read, named `PRODUCTION_<NAME>`:
   - Required:
     - `PRODUCTION_APP_DATABASE_URL`: the least-privilege login from
       `scripts/create_app_db_user.sql`, never the owner.
     - `PRODUCTION_SECRET_KEY`
     - `PRODUCTION_REDIS_URL`: production needs the worker.
   - Optional, passed when present: `SUPABASE_SECRET_KEY`, `EMAIL_API_KEY`, `SMTP_PASSWORD`, `TWILIO_ACCOUNT_SID`,
     `TWILIO_AUTH_TOKEN`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`,
     `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `VAPID_PRIVATE_KEY`, `SENTRY_DSN`.
     Staging uses the same names with `STAGING_`.
2. Give the Cloud Run runtime service account the Secret Accessor role on them.

**GitHub environment `production`** (Settings → Environments):
- **Protection:**
  - Required reviewers, so every release waits for an approval.
  - Deployment branches: `main` only.
- **Secrets:**
  - `GCP_SA_KEY` and `GCP_PROJECT_ID`: the deployer.
  - `PRODUCTION_DATABASE_URL`: the owner URL, used for migrations and the pre-deploy backup.
  - `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.
- **Variables:**
  - `BACKUP_BUCKET`
  - `RUNTIME_ENV`: plain settings as `KEY=VALUE` lines, e.g. `CORS_ORIGINS`, `EMAIL_PROVIDER`,
    `WEB_BASE_URL`, `SUPABASE_URL`, `STORAGE_TYPE`. A secret's name here is refused.
  - Optional:
    - `PG_VERSION`: the database's major version; default 17.
    - `RELEASE_IMAGE_REPOSITORY`: when staging's images live in another project.
    - `PRODUCTION_VPC_NETWORK` / `PRODUCTION_VPC_SUBNET`: for a Redis on a private network.
- Staging reads the same `RUNTIME_ENV` variable from its own `staging` environment.

**Vercel production environment:** set `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`,
`NEXT_PUBLIC_APP_URL` (the real domain) and `ENVIRONMENT=production`. Search engines may index
the site only with that last one set.

### 4.2 Releasing
1. Merge to `main`. The staging workflow builds the image, migrates staging, deploys and checks
   it.
2. Check staging.
3. Actions → **Production Deployment** → Run workflow, with the commit SHA.
   - The gate job refuses a commit that isn't on `main`, or whose staging readiness check
     didn't pass.
   - After approval, the release job:
     - takes a verified backup;
     - runs `alembic upgrade head`;
     - deploys the API, and checks `/health/ready` reports the new release;
     - deploys the worker, then the web app.
4. **Rollback:** the run summary lists the exact commands, for example
   `gcloud run services update-traffic flatmate-api --region asia-south1 --to-revisions=<previous>=100`.
   For the web app, use `vercel rollback`.
   - Rolling back code doesn't roll back the schema, so migrations must keep working with the
     previous release: add first, remove in a later release.
   - To undo the data side, restore the pre-deploy backup (4.4).

### 4.3 Backups
Every night at 03:00 IST, **Database Backup** dumps the database. It restores the dump into a
throwaway PostGIS + pgvector database and checks it against its manifest:
- the Alembic revision
- the row count of every table, taken from the same snapshot as the dump
- row-level security on the same tables, with the same number of policies

Only then does it upload the dump and manifest. A backup that doesn't restore fails the run, and
GitHub emails the failure. Every production release takes the same verified backup first
(`production/pre-deploy/`).

One-time setup:
```bash
gcloud storage buckets create gs://$BUCKET --location=asia-south1 \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://$BUCKET --clear-soft-delete \
  --lifecycle-file=infrastructure/backup/gcs-lifecycle.json
# Writers can add backups but not read, replace or delete them.
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=serviceAccount:$BACKUP_SA --role=roles/storage.objectCreator
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=serviceAccount:$DEPLOYER_SA --role=roles/storage.objectCreator
```

- **Retention:** backups are kept **30 days**; the lifecycle rule deletes them. Soft delete is
  off so a deleted backup is really gone.
- **Erased accounts:** data from an erased account is out of every backup within 30 days of
  erasure.
- **GitHub environment `production-backups`:** it has no reviewers, so the nightly run never
  waits.
  - Secret `BACKUP_DATABASE_URL`: the owner URL.
  - Secret `GCP_BACKUP_SA_KEY`: the backup service account.
  - Variable `BACKUP_BUCKET`.
- **Staging:** backups run by hand with the same names in the `staging` environment.
- **Supabase's own daily backups** (paid plans) are a second copy; these are the ones you can
  restore anywhere.
- **Not included:** uploaded files live in Supabase Storage, not in these backups.

### 4.4 Restoring
Never restore over a live database: restore into a new one and switch to it.
1. **Download** a dump and its `.manifest.json`. This needs Storage Object Viewer on the bucket,
   which a person holds, not CI:
   `gcloud storage cp "gs://$BUCKET/production/daily/<file>.dump*" .`
2. **Create an empty database**, either a new Supabase project or `CREATE DATABASE`.
3. **Restore and check.** This needs the PostgreSQL client tools, at least the server's version;
   set `PG_BIN` if they aren't on PATH. `--confirm-database` must name the target database:
   ```bash
   python scripts/db_backup.py restore --dump <file>.dump \
     --target-url "postgresql://postgres:<password>@<host>:5432/<db>" --confirm-database <db>
   ```
   - The tool refuses a target that already has tables.
   - It creates the extensions and roles the schema needs.
   - It restores in one transaction, then compares the result with the manifest. Exit code 0
     means it matched.
4. **Switch over:**
   - Create the app login on the new database (`scripts/create_app_db_user.sql`).
   - Update `PRODUCTION_APP_DATABASE_URL` in Secret Manager, and `PRODUCTION_DATABASE_URL` /
     `BACKUP_DATABASE_URL` in GitHub.
   - Re-run **Production Deployment** with the current release.
   - Check `/health/ready`.
5. **What's lost:** anything written since that backup, so up to a day, or less after a release.

## 5. Local Staging Reference Verification

The platform has been empirically verified on local reference staging:
- Frontend: `http://localhost:3001` (32 routes compiled, 31 automated tests passing)
- Backend: `http://localhost:8001` (110 routes registered, 136 automated tests passing)
- PostgreSQL: `localhost:5432/flatmate_staging_disposable` (43 tables present, 0 schema drift)
- Security & Privacy: 100% boundary enforcement (BOLA, DPDP address masking, coordinate fuzzing)
