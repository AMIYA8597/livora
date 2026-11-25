# Production Deployment & Infrastructure Runbook

**Target Architecture:** Free-First, Provider-Independent Modular Monolith  
**Primary Database:** Supabase PostgreSQL (or self-hosted PostgreSQL 16 with PostGIS & pgvector)  
**Containerization:** Multi-stage Docker + Docker Compose  

> **Launching with no budget?** [FREE_TIER_LAUNCH.md](FREE_TIER_LAUNCH.md) is the complete,
> scripted procedure for a ₹0 production on student offers: an Azure for Students VM running
> Caddy, the API, the worker and Redis; Supabase Free; and Vercel Hobby. It's deployed by
> `free-tier-deploy.yml` and tested by `free-tier-stack.yml`. The Cloud Run setup below is the
> paid path for 10,000 people at once (CAPACITY_PLAN.md).

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


## Capacity and traffic (10,000 people at once)

[CAPACITY_PLAN.md](CAPACITY_PLAN.md) holds the design, the load-test results, the sizing and
the runbook. What the deploy does:

- **API (`flatmate-api`):**
  - sized by the production workflow's defaults: min 2, max 30, concurrency 80, 1 vCPU, 1 GiB,
    timeout 60 s;
  - startup CPU boost, and probes on `/health/live`;
  - `WEB_CONCURRENCY` follows the vCPUs (`scripts/deploy_runtime.py --api-workers`).
- **Realtime (`flatmate-realtime`):**
  - the same image, for sockets: min 2, max 20, 1,000 sockets each, 2 GiB, a one-hour
    timeout, CPU always on;
  - it needs Redis, and the deploy stops if Redis is missing;
  - set the web app's `NEXT_PUBLIC_WS_URL` to `wss://<realtime-url>/api/v1/messaging/ws`.
    The deploy summary prints it.
- **Overrides:** GitHub variables, no code edit needed:
  - `API_MIN_INSTANCES`, `API_MAX_INSTANCES`, `API_CONCURRENCY`, `API_CPU`, `API_MEMORY`;
  - `REALTIME_SERVICE`, `REALTIME_MIN_INSTANCES`, `REALTIME_MAX_INSTANCES`.
- **The database must hold that many clients.** Each API process opens up to 15 connections
  and each realtime process up to 10, which is about 665 pooler clients at the maximums.
  Supabase's Free/Nano plan allows 200, so upgrade to Large or XL before launch, and use the
  transaction pooler (port 6543).
- **Monitoring:** apply `infrastructure/monitoring/` (a dashboard and four alert policies)
  with the commands in CAPACITY_PLAN.md section 5, and add a notification channel.
- **Load tests:** `loadtests/` (README there). Run the 10,000-user rehearsal on staging, sized
  like production, before launch.
