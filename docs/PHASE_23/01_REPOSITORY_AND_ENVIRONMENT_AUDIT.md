# PHASE 23.1 — Complete Repository and Environment Audit

**Document Version:** 1.0  
**Phase:** 23.1 — Complete Repository & Environment Audit  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Systems Architect, Application Security Engineer, Database Reliability Engineer  
**Classification:** Empirical Architecture, Codebase & Environment Audit  
**Project:** Flatmate Compatibility & Rental Marketplace  
**Monorepo Root:** `d:\work\flatmate`  

---

## 1. Executive Summary

This comprehensive audit evaluates the existing Flatmate Compatibility & Rental Marketplace repository in its entirety. The codebase is organized as a Turborepo-managed monorepo with pnpm workspaces containing a Next.js 14 App Router frontend (`apps/web`), a FastAPI Python 3.11/3.13 backend (`apps/api`), shared TypeScript contracts (`packages/contracts`), a shared Tailwind component library (`packages/ui`), database migrations and RLS policies (`database/`), and operational validation scripts (`scripts/`).

Every architecture layer, execution path, integration surface, and configuration loader was inspected and independently verified against source code rather than historical claims.

---

## 2. Monorepo & Build System Architecture

| Workspace Package | Path | Type / Runtime | Purpose | Dependencies & Status |
| :--- | :--- | :--- | :--- | :--- |
| **Monorepo Root** | `/` | pnpm 9.1.0, Turbo 2.0.0 | Orchestrates monorepo builds, linting, formatting | Valid `package.json`, `pnpm-workspace.yaml`, `turbo.json` |
| **`@flatmate/web`** | `apps/web` | Next.js 14.2.4 (App Router) | Responsive SSR & CSR Marketplace Frontend | 32 prerendered & dynamic routes; compiles cleanly |
| **`@flatmate/api`** | `apps/api` | FastAPI 0.111.0, Python 3.11+ | Primary REST & WebSocket Business API & Auth boundary | 110 endpoints, SQLAlchemy 2.0, Alembic, asyncpg |
| **`@flatmate/contracts`**| `packages/contracts` | TypeScript 5.4.5 | Canonical DTO definitions, enums & API interfaces | Synchronized with Pydantic schemas |
| **`@flatmate/ui`** | `packages/ui` | React 18, Tailwind CSS | Shared UI component primitives (Button, Modal, etc.) | Tailwind Base preset configured |

---

## 3. Actual Frontend Architecture (`apps/web`)

- **Framework & Routing:** Next.js 14.2.4 App Router (`apps/web/app`). Prerenders 32 static and dynamic routes.
- **Client/Server Split:** Server components used where appropriate; client components (`"use client"`) used for interactive forms, search filters, chat, and matching cards.
- **Supabase Integration Helpers:**
  - `apps/web/utils/supabase/client.ts`: Uses `@supabase/ssr` `createBrowserClient` with `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
  - `apps/web/utils/supabase/server.ts`: Uses `@supabase/ssr` `createServerClient` with cookie-backed session storage.
  - `apps/web/utils/supabase/middleware.ts`: Implements cookie refresh and session preservation.
  - `apps/web/middleware.ts`: Next.js middleware intercepting protected routes (`/dashboard`, `/profile`, `/owner`, `/admin`, `/messages`, `/appointments`).
- **API Client:** Centralized HTTP client in `apps/web/lib/api-client.ts` implementing RFC 7807 problem details parsing, Bearer token injection, request timeouts, and error handling.
- **State Management & UI Primitives:** React hooks (`useState`, `useEffect`, `useCallback`), `@flatmate/ui` shared components, Lucide React icons, Tailwind CSS responsive utility classes.

---

## 4. Actual Backend Architecture (`apps/api`)

- **Framework:** FastAPI 0.111.0 running on Uvicorn ASGI.
- **Application Structure:** Domain-driven modular structure under `apps/api/app/modules/`:
  - `administration`: Admin user management, role assignment, system stats.
  - `applications`: Tenancy applications lifecycle (`submitted`, `under_review`, `approved`, `rejected`).
  - `appointments`: Property viewings schedule, status progression, cancellation.
  - `auth`: Supabase JWT verification, local token validation, password recovery, session verification.
  - `flatmates`: Flatmate profile discovery, compatibility queries.
  - `groups`: Group syndicates, invitations, wishlist item voting, group compatibility.
  - `lifestyle`: Lifestyle quiz, 10-dimension questionnaire, dealbreakers.
  - `locations`: Hierarchical locations (India: States, Cities, Localities).
  - `matching`: Deterministic 10-dimension compatibility scoring, dealbreaker enforcement, recommendation feed.
  - `messaging`: Direct and group messaging, attachments, read cursors, notifications, WebSocket gateway.
  - `moderation`: User/listing reporting, block lists, admin moderation queues.
  - `notifications`: In-app notification delivery, unread counters.
  - `owners`: Landlord dashboard, property portfolio, tenant roster.
  - `pg_management`: Paying Guest building, floor, room, and bed inventory.
  - `profiles`: User profiles, privacy settings, Indian name & phone formatting.
  - `properties`: Property listings, amenities, images, room/bed assignment.
  - `search`: Geospatial and token-based property/flatmate search.
  - `storage`: S3/MinIO and Supabase Storage abstraction layer with MIME validation.
  - `subscriptions`: Premium tiers, mock/Razorpay payment contracts.
  - `tenants`: Roommate replacement vacancies and existing tenancy memberships.
  - `users`: Core identity models, RBAC roles.
  - `verification`: Trust & verification document upload and admin approval.

---

## 5. Database and Migration Architecture

- **ORM & Authority:** SQLAlchemy 2.0.31 with asyncpg (`postgresql+asyncpg://`) for async FastAPI operations and psycopg2 for sync migrations and scripts.
- **Migration Authority:** Alembic (`apps/api/alembic.ini`, `apps/api/migrations/`).
  - Current Revision Head: `002_messaging_realtime` (revises `001_initial_schema`).
  - Alembic tables: `alembic_version` stores migration state.
- **Model vs Schema Parity:**
  - 42 domain models declared in SQLAlchemy.
  - 43 database tables present in reference database (42 domain tables + `alembic_version`).
  - Zero column discrepancies, zero missing tables, zero type drifts.
- **Extensions Used:**
  - `uuid-ossp`: UUID primary key generation.
  - `pg_trgm`: Trigram fuzzy text matching for search.
  - PostGIS & pgvector: Configured conditionally with graceful fallback if underlying PostgreSQL image does not load binary C-extensions.

---

## 6. Authentication & Authorization Flow

- **Identity Provider:** Supabase Auth (`https://qjwitdovbsfviaepjcul.supabase.co`).
- **Token Format:** Signed JWTs (ES256 / HS256).
- **Backend Verification Strategy:**
  - `SUPABASE_JWKS_URL`: `https://qjwitdovbsfviaepjcul.supabase.co/auth/v1/.well-known/jwks.json` used for RS256/ES256 signature verification.
  - Legacy HS256 JWT Secret fallback supported for existing tokens.
  - Claims validated: `iss` (matches Supabase URL), `aud` (`authenticated`), `exp` (timestamp validity).
- **Authorization Boundary:**
  - FastAPI server-side role validation (`UserRole`: `seeker`, `owner`, `existing_tenant`, `pg_operator`, `group_member`, `moderator`, `admin`).
  - Resource ownership checks: Endpoints check `user_id == current_user.id` or appropriate role prior to granting read/write operations.
  - Route guards in frontend middleware do NOT replace backend authorization.

---

## 7. Storage Architecture

- **Storage Provider:** Supabase Cloud Storage API over HTTPS port 443.
- **Configured Buckets:**
  1. `property-photos` (Public: True, Max 10MB, Images only)
  2. `properties` (Public: True, Max 10MB, Images only)
  3. `avatars` (Public: True, Max 5MB, Images only)
  4. `verification-docs` (Private: True, Max 10MB, PDF/JPEG/PNG)
  5. `verification` (Private: True, Max 10MB, PDF/JPEG/PNG)
  6. `chat-attachments` (Private: True, Max 25MB, Documents & Images)
- **Security:**
  - Magic byte validation (`python-magic` / file signatures) prevents MIME spoofing.
  - Signed URLs with expiration (default 3600s) generated for private documents.
  - No service keys exposed to browser clients.

---

## 8. WebSocket and Distributed Event Architecture

- **WebSocket Gateway:** `/api/v1/messaging/ws` with Bearer query parameter or header authentication.
- **Event Distribution:**
  - In-memory Pub/Sub broker for single-instance local testing.
  - Redis Pub/Sub event bus configured for distributed multi-instance deployment (`REDIS_URL`).
  - Outbox pattern implemented via `outbox_events` table for resilient event delivery.
- **Features:** Message delivery confirmations, read cursors, presence indicators, conversation subscriptions.

---

## 9. AI/ML Implementation and Limitations

- **Current Implementation:** Deterministic rule-based scoring engine (`app/modules/matching/service.py`).
- **Dimensions (10):**
  1. Sleep Schedule (Chronotype)
  2. Cleanliness & House Chores
  3. Noise Tolerance
  4. Social Habits & Gathering Frequency
  5. Food / Diet Preferences (Vegetarian, Non-veg, Vegan)
  6. Smoking & Drinking Habits
  7. Pet Preferences
  8. Work from Home (WFH) Patterns
  9. Guest & Visitor Policy
  10. Budget & Locality Alignment
- **Weights & Dealbreakers:**
  - Strict 100% normalized weight sum.
  - Hard dealbreakers (e.g., smoking mismatch) cap compatibility at 30.0%.
- **Search:** Trigram & token-projection query vector search.
- **Clarification:** This is NOT a deep neural network or large language model. It is a deterministic, highly explainable, mathematically rigorous heuristic engine. Outdated documentation claiming "deep learning NLP" is flagged as inaccurate.

---

## 10. External Integrations Status

| External Integration | Target | Status | Connectivity Details |
| :--- | :--- | :--- | :--- |
| **Supabase Auth** | `https://qjwitdovbsfviaepjcul.supabase.co` | **CONNECTED & VERIFIED** | Live user provisioning, password grant, JWT verification verified. |
| **Supabase Storage** | `https://qjwitdovbsfviaepjcul.supabase.co` | **CONNECTED & VERIFIED** | 6 live cloud buckets; public & signed upload/download verified. |
| **Supabase PostgREST** | `https://qjwitdovbsfviaepjcul.supabase.co` | **CONNECTED (EMPTY SCHEMA)** | HTTP 200 via HTTPS; public schema currently has 0 exposed tables. |
| **Hosted PostgreSQL (Direct TCP)** | `aws-1-ap-south-1.pooler.supabase.com:5432/6543` | **FIREWALLED** | Outbound TCP ports 5432 and 6543 dropped by local network egress firewall. |
| **Local Staging DB** | `localhost:5432/flatmate_staging_disposable` | **CONNECTED & VERIFIED** | PostgreSQL 18.0, 43 tables, Alembic head `002_messaging_realtime`. |
| **Redis** | `redis://localhost:6379/0` | **CONNECTED** | Used for rate limiting, session caching, and pub/sub messaging. |

---

## 11. Test & Build Status Summary

- **Backend Pytest Suite:** 136 tests collected, **136 passed** (100% pass rate).
- **Frontend Web Suite:** 31 tests collected, **31 passed** (100% pass rate).
- **Next.js Production Build:** 32 routes compiled, static generation **32/32 successful**, 0 TypeScript errors.
- **Schema Parity:** 42 SQLAlchemy domain models match 43 database tables with 0 column drift.

---

## 12. Technical Debt, Security Concerns & Outdated Documentation

1. **Local Egress Firewall Barrier:**
   - Outbound ports 5432/6543 are blocked by local perimeter network policy. HTTPS port 443 is unrestricted.
   - Mitigated for API, Auth, and Storage; direct database wire operations (Alembic over wire) require network permit or HTTPS-based migration invocation.
2. **Outdated Documentation Claims:**
   - Previous docs referred to "AI Deep Learning embeddings" for compatibility; verified implementation is a deterministic 10-dimension weighted heuristic.
   - Previous docs mentioned Prisma; verified that SQLAlchemy 2.x and Alembic are the sole ORM and migration authority.
3. **Secret Hygiene:**
   - Exposed Supabase secrets in conversation prompts require rotation before production deployment.
   - Zero secrets committed to Git repository.
