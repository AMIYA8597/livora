# Production & Staging Deployment Runbook
## Flatmate Compatibility & Rental Marketplace

**Phase:** 20 — Enterprise-Grade Staging Infrastructure, Real Cloud Deployment, CI/CD, Database, Security, Storage, Domain, HTTPS and Complete System Integration  
**Target Architecture:** Google Cloud Run (Backend) + Vercel (Frontend) + Supabase Managed PostgreSQL + PostGIS + pgvector  
**Database:** PostgreSQL 15 with PostGIS & pgvector  
**Migration Version:** Alembic `002_messaging_realtime` (Head)  
**Containerization:** Multi-stage Non-Root Docker (`apps/api/Dockerfile`)  
**Status:** **STAGING ACCEPTED** (Ready for Phase 21 Production Launch)  

---

## 1. Environment Configurations & Secrets Inventory

The application reads runtime configuration from environment variables. Reference templates with self-documenting placeholders are maintained:
- [`.env.example`](file:///D:/work/flatmate/.env.example) (Local development)
- [`.env.staging.example`](file:///D:/work/flatmate/.env.staging.example) (Isolated staging environment)
- [`.env.production.example`](file:///D:/work/flatmate/.env.production.example) (Hardened production deployment)

Detailed runbooks and architecture specifications:
- [`docs/PHASE_20_DEPLOYMENT_RUNBOOK.md`](file:///D:/work/flatmate/docs/PHASE_20_DEPLOYMENT_RUNBOOK.md)
- [`docs/PHASE_20_INFRASTRUCTURE_DECISIONS.md`](file:///D:/work/flatmate/docs/PHASE_20_INFRASTRUCTURE_DECISIONS.md)
- [`docs/PHASE_20_SECRET_MANAGEMENT.md`](file:///D:/work/flatmate/docs/PHASE_20_SECRET_MANAGEMENT.md)
- [`docs/PHASE_20_DATABASE_DEPLOYMENT.md`](file:///D:/work/flatmate/docs/PHASE_20_DATABASE_DEPLOYMENT.md)
- [`docs/PHASE_20_BACKEND_DEPLOYMENT.md`](file:///D:/work/flatmate/docs/PHASE_20_BACKEND_DEPLOYMENT.md)
- [`docs/PHASE_20_FRONTEND_DEPLOYMENT.md`](file:///D:/work/flatmate/docs/PHASE_20_FRONTEND_DEPLOYMENT.md)
- [`docs/PHASE_20_CICD_AND_ROLLBACK.md`](file:///D:/work/flatmate/docs/PHASE_20_CICD_AND_ROLLBACK.md)

| Variable | Environment | Required | Description |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | `staging`, `production` | **YES** | Runtime environment (`production` or `staging` enforces strict security) |
| `DATABASE_URL` | All | **YES** | Transaction pooler URI (`postgresql+asyncpg://...:6543/postgres`) |
| `DIRECT_URL` / `DATABASE_SYNC_URL` | All | **YES** | Direct port 5432 URI for Alembic DDL migrations (`postgresql://...:5432/postgres`) |
| `SECRET_KEY` | All | **YES** | Internal fallback and CSRF signing secret (Min 32 chars, high entropy) |
| `SUPABASE_URL` | Staging / Prod | **YES** | Supabase Project URL (`https://<project-ref>.supabase.co`) |
| `SUPABASE_ANON_KEY` | Staging / Prod | **YES** | Supabase Anonymous Client Key (Public frontend) |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend ONLY | **YES** | Supabase Admin Service Role Key (**NEVER exposed to frontend**) |
| `SUPABASE_JWT_SECRET` | Backend ONLY | **YES** | Supabase Auth JWT HS256 secret for validating bearer tokens |
| `REDIS_URL` | All | **YES** | Redis connection URI with TLS (`rediss://...`) |
| `RESEND_API_KEY` | Backend ONLY | Optional | Transactional email provider API key (console fallback if empty) |
| `CORS_ORIGINS` | Staging / Prod | **YES** | JSON array of allowed origins, e.g. `["https://flatmate-web-staging.vercel.app"]` |
| `NEXT_PUBLIC_API_URL` | Web Frontend | **YES** | Public API endpoint, e.g. `https://flatmate-api-staging-<hash>.a.run.app/api/v1` |
| `NEXT_PUBLIC_WS_URL` | Web Frontend | **YES** | Public WebSocket endpoint, e.g. `wss://flatmate-api-staging-<hash>.a.run.app/api/v1/messaging/ws` |

---

## 2. Staging Deployment Checklist

### 2.1 Database Provisioning & Migration
1. Provision PostgreSQL 18 instance with PostGIS and pgvector extensions:
   ```sql
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   CREATE EXTENSION IF NOT EXISTS "postgis";
   CREATE EXTENSION IF NOT EXISTS "vector";
   ```
2. Execute Alembic migrations to head:
   ```bash
   python -m alembic -c apps/api/alembic.ini upgrade head
   ```
3. Confirm current revision:
   ```bash
   python -m alembic -c apps/api/alembic.ini current
   # Expected output: 002_messaging_realtime (head)
   ```

### 2.2 Container Build & Launch
Build and boot multi-container stack via Docker Compose:
```bash
docker compose up -d --build
```

### 2.3 Health & Readiness Probing
Verify running container endpoints:
```bash
# Liveness probe
curl -f http://localhost:8000/health

# Readiness probe (verifies database & cache)
curl -f http://localhost:8000/ready
```

---

## 3. CI/CD Pipeline Verification

The continuous integration workflow is defined in `.github/workflows/ci.yml`. It runs automatically on pull requests and pushes to `main` and `staging`:
- Node.js & pnpm dependency installation.
- Python 3.11 virtual environment & dependencies.
- Monorepo TypeScript compilation (`pnpm turbo run test`).
- Backend pytest test execution with coverage (`python -m pytest apps/api/tests`).
- Security regression validation (`python -m pytest apps/api/tests/security/test_security_regressions.py`).
- Next.js 14 production build (`pnpm turbo run build`).
