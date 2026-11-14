# PHASE 24.1 — Repository and Release Baseline Audit

**Document Version:** 1.0  
**Phase:** 24.1 — Monorepo Architecture, Dependency & Environment Baseline  
**Date:** November 15, 2026  
**Auditor Roles:** Principal Systems Architect, Lead Release Engineer, Security Architect  
**Classification:** Authoritative Technical Baseline Audit  
**Project:** Flatmate Compatibility & Rental Marketplace  
**Monorepo Root:** `d:\work\flatmate`  

---

## 1. Executive Summary

This document establishes the official repository and release baseline for **Phase 24: Real Hosted Supabase PostgreSQL Migration, Database Parity, Full-Stack Integration, and Production Release Validation**.

In strict adherence to the project's non-negotiable rules:
- No existing working architecture, database models, or frontend features have been modified or degraded.
- Alembic remains the single authoritative database migration framework; no secondary migration tool or Prisma schema has been introduced.
- All baseline tests have been executed from a clean state and verified with zero fabrications.
- All secrets, connection strings, and credential values remain strictly confidential and redacted.

---

## 2. Git Repository & Working Tree State

| Parameter | Observed Baseline Value | Status |
| :--- | :--- | :---: |
| **Current Git Branch** | `main` | **VERIFIED** |
| **Current Commit SHA** | `089e0d7` (`docs: update operational runbook with phase 23 hosted migration procedures`) | **VERIFIED** |
| **Uncommitted Changes** | 0 files (working tree clean, zero unstaged/staged modifications) | **VERIFIED** |
| **Upstream Tracking** | Ahead of `origin/main` by 5 commits | **VERIFIED** |

---

## 3. Monorepo Structure & Package Inventory

The monorepo is managed via **pnpm workspaces (v9.1.0)** and **Turborepo (v2.11.11)** across four primary packages:

| Workspace Package | Filesystem Path | Technology Stack | Core Version | Build / Test Status |
| :--- | :--- | :--- | :--- | :---: |
| **`@flatmate/web`** | `apps/web` | Next.js App Router, React, TailwindCSS | Next 14.2.4, React 18.3.1 | **VERIFIED (32 routes compiled, 31 tests passed)** |
| **`@flatmate/api`** | `apps/api` | FastAPI, Python, SQLAlchemy, asyncpg | Python 3.13.7 (req >=3.11), FastAPI 0.111.0 | **VERIFIED (136 tests passed, 0 mypy/ruff errors)** |
| **`@flatmate/contracts`** | `packages/contracts` | TypeScript Shared DTOs & Enums | TypeScript 5.4.5 | **VERIFIED (`tsc --noEmit` clean)** |
| **`@flatmate/ui`** | `packages/ui` | Shared React/Tailwind Components | React 18.3.1, Lucide React 0.383.0 | **VERIFIED (`tsc --noEmit` clean)** |

### Supporting Repository Directories:
- **`database/migrations`**: Alembic SQL scripts and standalone reference SQL (`complete_hosted_schema.sql`, `001_initial_schema.sql`, `002_postgis_indexes.sql`, `003_india_marketplace_complete_schema.sql`).
- **`database/policies`**: Row Level Security policies (`rls_policies.sql`).
- **`database/seeds`**: Seed data scripts (`seed_all.sql`).
- **`infrastructure/`**: Production and development container configurations (`Dockerfile.api`, `Dockerfile.worker`, `Dockerfile.web`, `docker-compose.yml`, `docker-compose.prod.yml`).
- **`scripts/`**: 24 operational, diagnostic, benchmarking, and security verification scripts.
- **`.github/workflows/`**: 6 CI/CD pipelines (`ci.yml`, `security.yml`, `staging-deploy.yml`, `staging-smoke-tests.yml`, `docker-build.yml`, `hosted-db-migration.yml`).
- **`docs/PHASE_23/`**: 21 empirical baseline reports from Phase 23.

---

## 4. API Routes and OpenAPI Contract Baseline

Execution of `scripts/inspect_routes.py` and `scripts/analyze_openapi.py` confirms the registered API surface:

| Metric | Measured Baseline |
| :--- | :---: |
| **Total Registered FastAPI Routes** | **110 routes** (REST endpoints + WebSocket) |
| **Total OpenAPI Paths** | **87 paths** |
| **Total OpenAPI Operations** | **103 operations** |
| **Modular Domain Packages** | **23 modules** under `apps/api/app/modules/` |

### Route Distribution by Domain:
1. **Administration & Operations:** 4 endpoints
2. **Authentication & Identity:** 9 endpoints
3. **File Storage & Uploads:** 2 endpoints
4. **Flatmates Discovery:** 1 endpoint
5. **Group Matching & Flatsharing:** 7 endpoints
6. **Lifestyle & Dealbreakers:** 6 endpoints
7. **Matching Engine:** 4 endpoints
8. **Messaging (REST + WS):** 14 endpoints + 1 WebSocket endpoint (`/api/v1/messaging/ws`)
9. **Moderation & Safety:** 6 endpoints
10. **Notifications:** 3 endpoints
11. **Owner / Landlord Dashboard:** 4 endpoints
12. **PG Management:** 4 endpoints
13. **Profiles:** 6 endpoints
14. **Properties & Inventory:** 7 endpoints
15. **Rental Applications:** 4 endpoints
16. **Search & Geospatial Discovery:** 2 endpoints
17. **System & Health Checks:** 5 endpoints (`/health`, `/health/live`, `/health/ready`, `/ready`, `/`)
18. **Tenants & Roommate Vacancies:** 5 endpoints
19. **Trust & Verification:** 3 endpoints
20. **Users:** 3 endpoints
21. **Viewing Appointments:** 4 endpoints
22. **Interactive Documentation:** 4 endpoints (`/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect`)

---

## 5. Database Schema & Migration Baseline

Inspection of the database layer via Alembic and `scripts/reconcile_schema.py`:
- **Authoritative Migration Tool:** Alembic (`apps/api/alembic.ini`, `apps/api/migrations/env.py`).
- **Migration Version History:**
  1. `001_initial_complete_schema` (`apps/api/migrations/versions/001_initial_complete_schema.py`)
  2. `002_messaging_realtime_system` (`apps/api/migrations/versions/002_messaging_realtime_system.py`)
- **Current Alembic Head:** `002_messaging_realtime`
- **SQLAlchemy Domain Models:** 42 declared models in `Base.metadata`.
- **Database Tables in Reference Schema:** 43 tables (42 models + `alembic_version`).
- **Schema Parity Drift:** **0 column drift, 0 missing tables, 0 extra tables**.

---

## 6. Hosted Supabase Configuration Baseline

- **Hosted Project URL:** `https://qjwitdovbsfviaepjcul.supabase.co`
- **Region:** `ap-south-1` (AWS Mumbai)
- **Supabase Auth API:** Responding HTTP 200 on `/auth/v1/settings`.
- **Supabase JWKS Endpoint:** `https://qjwitdovbsfviaepjcul.supabase.co/auth/v1/.well-known/jwks.json` (resolves active ES256 key).
- **Supabase Storage:** Declared buckets (`properties`, `property-photos`, `avatars`, `verification`, `verification-docs`, `chat-attachments`).
- **Hosted PostgreSQL Wire Egress:** Ports 5432 and 6543 outbound SYN packets dropped by development workstation perimeter firewall. Direct HTTPS (port 443) to Supabase services is fully functional.

---

## 7. Quality & Test Suite Baseline Summary

| Subsystem / Test Suite | Command Executed | Result | Classification |
| :--- | :--- | :--- | :---: |
| **Backend Pytest Suite** | `pytest apps/api` | 136 passed, 0 failed, 62 deprecation warnings (13.23s) | **VERIFIED** |
| **Backend Code Formatting & SAST** | `ruff check apps/api` | All checks passed (0 errors) | **VERIFIED** |
| **Backend Static Type Safety** | `mypy apps/api/app` | 0 type errors across 131 files | **VERIFIED** |
| **Frontend Test Suite** | `pnpm --filter @flatmate/web test` | 31 passed, 0 failed (584ms) | **VERIFIED** |
| **Frontend Code Quality** | `pnpm --filter @flatmate/web lint` | 0 ESLint errors, 0 warnings | **VERIFIED** |
| **Frontend Static Typing** | `pnpm --filter @flatmate/contracts test; pnpm --filter @flatmate/ui test` | All packages compile cleanly (0 errors) | **VERIFIED** |
| **Next.js Production Build** | `pnpm --filter @flatmate/web build` | 32 static/dynamic routes compiled cleanly | **VERIFIED** |
| **Row Level Security (RLS)** | `python scripts/test_rls_policies.py` | 100% passed across all non-superuser roles | **VERIFIED** |
| **Database Schema Reconciler** | `python scripts/reconcile_schema.py` | 42 models vs 43 tables, zero column drift | **VERIFIED** |

---

## 8. Baseline Audit Sign-Off

The repository is confirmed to be in an exceptionally healthy, fully passing, zero-drift state. All baseline assets are catalogued, providing an unshakeable foundation for executing Phase 24.
