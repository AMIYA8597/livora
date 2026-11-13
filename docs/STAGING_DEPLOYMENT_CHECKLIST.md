# Phase 16 Staging Deployment Readiness Checklist
## Flatmate Compatibility & Rental Marketplace Release Candidate

**Audit Date:** 2026-11-13  
**Auditor:** Principal Software Architect & Release Auditor  
**Candidate Status:** **CONDITIONALLY READY**  

---

## 1. Executive Deployment Readiness Summary

| Component | Status | Verification Evidence | Action Required Before Production |
| :--- | :--- | :--- | :--- |
| **Backend API** | **READY** | 75 unit/integration/security tests passing; all endpoints functional | Deploy container to staging cluster |
| **Frontend Web App** | **READY** | Turborepo build 12/12 routes passing, TypeScript 0 errors | Configure `NEXT_PUBLIC_API_URL` on CDN/Vercel |
| **Shared Contracts** | **READY** | Synchronized with OpenAPI schema; contract tests passing | Published internally as workspace package |
| **Alembic Migrations** | **READY** | `001_initial_complete_schema.py` verified; upgrade/downgrade functional | Run `alembic upgrade head` on staging DB |
| **Database Extensions**| **CONDITIONAL** | `uuid-ossp` and `pg_trgm` active. `postgis` & `vector` require target PG environment | Provision Supabase or Linux PG 16 container with PostGIS & pgvector |
| **Supabase Auth** | **CONDITIONAL** | Token validation logic verified; production fail-closed active | Input live `SUPABASE_URL` and `SUPABASE_JWT_SECRET` |
| **Storage Infrastructure** | **CONDITIONAL** | Local & Supabase adapters implemented; resilience tests passing | Provision `flatmate-media` bucket in Supabase dashboard |
| **Docker Engine** | **CONDITIONAL** | Dockerfiles, Compose prod, and Nginx valid. Local Windows daemon was offline | Run `docker compose -f docker-compose.prod.yml up` on staging server |

---

## 2. Pre-Flight Staging Checklist

### 2.1 Database Setup
- [x] Schema DDL verified with all relational constraints and foreign keys.
- [x] Check constraints for capacity invariants verified (`current_occupants <= max_capacity`, `occupied_beds <= max_beds`).
- [x] Seed script safety guard implemented (refuses to wipe in `ENVIRONMENT=production`).
- [ ] Connect staging Supabase instance and run:
  ```bash
  cd apps/api
  python -m alembic upgrade head
  ```

### 2.2 Security Hardening
- [x] SEC-01 Fixed: Application IDOR eliminated with owner/admin authorization check.
- [x] SEC-02 Fixed: Appointment IDOR eliminated with strict participant check.
- [x] SEC-03 Fixed: Group member injection restricted to creator/leader.
- [x] SEC-04 Fixed: Wishlist voting restricted to active group members.
- [x] SEC-05 Fixed: Exact residential addresses masked; fuzzed coordinates (~1.1 km) returned in search.
- [x] SEC-06 Fixed: Insecure native JWT fallback disabled in non-development environments.
- [x] SEC-07 Fixed: Bed assignment race condition locked with `with_for_update()`.
- [x] SEC-08 Fixed: Raw survey answer leakage eliminated in compatibility reports.
- [x] RFC 7807 problem details error responses validated.
- [x] Rate limiting sliding window tested and verified.

### 2.3 Application & Frontend
- [x] All 75 pytest tests green (`pytest apps/api/tests`).
- [x] Python Ruff linting clean (`ruff check apps/api`).
- [x] Python Mypy strict type checking clean (100 files, 0 errors).
- [x] Next.js 14 production build succeeds (`pnpm turbo run build`).
- [x] Contract sync tests passing (`test_frontend_contracts_sync.py`).

---

## 3. Post-Deployment Verification Steps (Smoke Run)

1. **Health & Readiness Check:**
   ```bash
   curl -i https://staging-api.flatmate.internal/health
   curl -i https://staging-api.flatmate.internal/health/live
   curl -i https://staging-api.flatmate.internal/health/ready
   ```
2. **Authentication Smoke:**
   - Register a new test seeker: `POST /api/v1/auth/register`
   - Login: `POST /api/v1/auth/login`
   - Retrieve context: `GET /api/v1/auth/me`
3. **Property Discovery Smoke:**
   - Query properties: `GET /api/v1/properties?city=Bengaluru`
   - Check that `address_exact` is masked for public viewers.
4. **Matching & Compatibility Smoke:**
   - Submit lifestyle quiz: `POST /api/v1/lifestyle/quiz`
   - Calculate compatibility: `POST /api/v1/matching/calculate`
   - Confirm compatibility report details 10 dimensions without leaking counterparty raw inputs.
5. **WebSocket Chat Smoke:**
   - Establish connection: `wss://staging-api.flatmate.internal/api/v1/messaging/ws/{conversation_id}`
   - Exchange test message and confirm real-time receipt.
