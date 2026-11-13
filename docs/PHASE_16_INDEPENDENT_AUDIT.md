# Phase 16 — Independent Repository & Architecture Audit
## Flatmate Compatibility & Rental Marketplace

**Auditor:** Principal Software Architect & Independent Code Auditor  
**Audit Date:** 2026-11-13  
**Status:** **AUDIT COMPLETE — REMEDIATION REQUIRED**  
**Target Repository:** `flatmate-platform` (FastAPI + SQLAlchemy + Next.js Monorepo)

---

## 1. Executive Summary

This independent audit conducts a rigorous, evidence-based verification of the backend source code, database architecture, security controls, API specifications, and shared TypeScript contracts against the PRD and completion claims recorded in Phases 00–15.

While the modular monolith presents a structured foundation with comprehensive domain models and 69 local unit/mock tests, the audit has identified **critical discrepancies between documented specifications and actual code**, **severe security vulnerabilities (BOLA/IDOR)**, **database migration inconsistencies that would fail against real PostgreSQL**, and **out-of-sync frontend contracts**.

---

## 2. Comprehensive Findings Matrix

| Finding ID | Domain / Module | File Path | Severity | Problem Summary |
| :--- | :--- | :--- | :---: | :--- |
| **FIND-01** | Migrations / Alembic | `apps/api/migrations/` | **CRITICAL** | Alembic `versions/` folder is missing; zero migration history in Alembic. |
| **FIND-02** | Migrations / SQL | `database/migrations/001_initial_schema.sql` | **CRITICAL** | Raw SQL schema defines legacy property columns (`property_type`, `deposit`, `address`, `country='USA'`) missing 10+ columns required by SQLAlchemy models. |
| **FIND-03** | Authorization / IDOR | `apps/api/app/modules/applications/router.py` | **CRITICAL** | `GET /applications/{application_id}` does not verify applicant or owner identity, allowing any authenticated user to read private rental applications. |
| **FIND-04** | Authorization / BOLA | `apps/api/app/modules/appointments/router.py` | **CRITICAL** | `GET /appointments/{appointment_id}` is completely unauthenticated and unvalidated. |
| **FIND-05** | Authorization / BOLA | `apps/api/app/modules/groups/router.py` | **HIGH** | `POST /groups/{group_id}/members` does not verify caller is leader/member; any user can inject members into any group. |
| **FIND-06** | Authorization / BOLA | `apps/api/app/modules/groups/service.py` | **HIGH** | `POST /groups/{group_id}/wishlist/{property_id}/vote` allows non-members to vote on group wishlists. |
| **FIND-07** | Privacy / Geo Fuzzing | `apps/api/app/modules/search/service.py` | **HIGH** | Authenticated seekers receive un-fuzzed exact coordinates; distance calculations allow trilateration down to ~10m precision. |
| **FIND-08** | Privacy / Compatibility | `apps/api/app/modules/matching/engine.py` | **MEDIUM** | Compatibility explanations directly output target user's survey responses (e.g., diet, cleanliness level, work habits) in plaintext strings. |
| **FIND-09** | Security / Auth | `apps/api/app/core/config.py` & `security.py` | **HIGH** | Default hardcoded fallback JWT secret and insecure fallback mechanism; lacks JWKS / asymmetric key validation for Supabase RS256 tokens. |
| **FIND-10** | Storage Architecture | `apps/api/app/infrastructure/storage.py` | **MEDIUM** | Storage provider is disconnected; no endpoint performs file uploads, type validation, or generates signed URLs. |
| **FIND-11** | Concurrency / DB | `apps/api/app/modules/properties/service.py` | **HIGH** | `assign_bed_occupant` does not use `SELECT ... FOR UPDATE`, allowing race conditions on concurrent bed assignment despite ADR-004 claims. |
| **FIND-12** | Database RLS | `database/policies/rls_policies.sql` | **HIGH** | RLS policies rely on `current_setting('app.current_user_id')`, which the SQLAlchemy connection pool never sets per-session. |
| **FIND-13** | ML / Vector Search | `apps/api/app/modules/lifestyle/service.py` | **MEDIUM** | 64-dimensional embeddings are synthetic trigonometric functions, not a real semantic model; incompatible with standard 384/1536-dim embedding models. |
| **FIND-14** | API Spec Mismatch | `API_SPECIFICATION.md` | **MEDIUM** | Documented endpoints (`/domains`, `/rooms/{id}`, `DELETE /properties/{id}`, etc.) do not match actual FastAPI routes. |
| **FIND-15** | Frontend Contracts Drift | `packages/contracts/src/` | **HIGH** | `@flatmate/contracts` (`PropertyDTO`, `ScoreBreakdown`) does not match actual backend schemas (`PropertyResponse`, `ScoreBreakdownSchema`). |
| **FIND-16** | Code Duplication | `apps/api/app/infrastructure/geo.py` | **LOW** | `geo.py` is an unused duplicate of `geospatial.py`. |
| **FIND-17** | Unused Domain Modules | `apps/api/app/modules/professional_domains` | **LOW** | Contains `models.py` only; missing router, service, schemas. |

---

## 3. Detailed Audit Findings & Evidence

### FIND-01: Alembic Missing Versions Directory
- **File Path:** `apps/api/migrations/`
- **Module:** Database Migrations
- **Problem:** `alembic.ini` points to `migrations`, which contains `env.py` and `script.py.mako`, but no `versions/` folder exists. Running `alembic upgrade head` finds no revision scripts and performs no operations.
- **Severity:** **CRITICAL**
- **Evidence:** Directory listing of `apps/api/migrations` contains only `env.py` and `script.py.mako`. `DEPLOYMENT.md` instructs running `alembic upgrade head`, which is a no-op.
- **Recommended Correction:** Generate reproducible initial and incremental Alembic revision scripts under `apps/api/migrations/versions/` reflecting the full SQLAlchemy `Base.metadata`.

---

### FIND-02: SQL Migration Incompatibility with Application Models
- **File Path:** `database/migrations/001_initial_schema.sql` & `003_india_marketplace_complete_schema.sql`
- **Module:** Database Schema
- **Problem:** `001_initial_schema.sql` defines `properties` table with legacy columns:
  - `property_type` instead of `property_category`
  - `address` instead of `address_display` and `address_exact`
  - `deposit` instead of `security_deposit`
  - `country VARCHAR DEFAULT 'USA'` instead of `India`
  - Missing: `configuration`, `currency`, `maintenance_monthly`, `max_capacity`, `current_occupants`, `furnishing_status`, `listing_status`, `is_verified`
  `003_india_marketplace_complete_schema.sql` never alters `properties` to add these required columns. Running the app against a database built from these SQL files crashes immediately on any property query.
- **Severity:** **CRITICAL**
- **Evidence:** `apps/api/app/modules/properties/models.py` lines 15–58 require columns that do not exist in the SQL migrations.
- **Recommended Correction:** Update the SQL migration scripts to define the complete, accurate schema matching the SQLAlchemy models, or generate an Alembic migration that generates the full schema.

---

### FIND-03: Broken Object-Level Authorization (IDOR) on Applications
- **File Path:** `apps/api/app/modules/applications/router.py`
- **Function:** `get_application` (lines 31–41) & `ApplicationService.get_by_id`
- **Problem:** The endpoint receives `current_user` but never checks if `current_user.id == app.applicant_id` or `current_user.id == property.owner_id` or `current_user.role == 'admin'`. Any authenticated user can read any rental application across the system.
- **Severity:** **CRITICAL**
- **Evidence:**
  ```python
  @router.get("/{application_id}", response_model=ApplicationResponse)
  async def get_application(application_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
      service = ApplicationService(db)
      app = await service.get_by_id(application_id)
      if not app:
          raise NotFoundException("Application not found")
      return app
  ```
- **Recommended Correction:** Verify authorization: ensure caller is the applicant, the property owner, or an administrator; return HTTP 403 Forbidden otherwise.

---

### FIND-04: Unauthenticated Information Disclosure on Appointments
- **File Path:** `apps/api/app/modules/appointments/router.py`
- **Function:** `get_appointment` (lines 38–47)
- **Problem:** The route lacks the `Depends(get_current_user)` dependency completely. Any unauthenticated caller can query `GET /api/v1/appointments/{appointment_id}` to retrieve applicant IDs, host IDs, appointment time, and meeting links.
- **Severity:** **CRITICAL**
- **Evidence:**
  ```python
  @router.get("/{appointment_id}", response_model=AppointmentResponse)
  async def get_appointment(appointment_id: UUID, db: AsyncSession = Depends(get_db)):
      service = AppointmentService(db)
      appt = await service.get_by_id(appointment_id)
  ```
- **Recommended Correction:** Add `current_user: User = Depends(get_current_user)` and verify that `current_user.id` is either `appt.applicant_id`, `appt.host_id`, or an administrator.

---

### FIND-05: Broken Group Membership Authorization (BOLA)
- **File Path:** `apps/api/app/modules/groups/router.py` & `service.py`
- **Function:** `add_group_member` (lines 50–59)
- **Problem:** `add_group_member` takes `data: AddMemberRequest` and adds the member without validating whether `current_user.id` is the group leader or creator. An arbitrary user can force any user into any group and assign them arbitrary roles (even `'leader'`).
- **Severity:** **HIGH**
- **Evidence:** `GroupService.add_member` only checks if the user is already a member; caller authorization is omitted.
- **Recommended Correction:** Verify that `current_user.id == group.creator_id` or that `current_user` is a group member with leader privileges before adding members.

---

### FIND-06: Unauthorized Wishlist Voting (BOLA)
- **File Path:** `apps/api/app/modules/groups/service.py`
- **Function:** `vote_wishlist` (lines 216–237)
- **Problem:** Any authenticated user can vote on or add items to any group's property wishlist without being a member of that group.
- **Severity:** **HIGH**
- **Evidence:** `vote_wishlist` performs no membership verification query before recording votes in `GroupWishlistItem`.
- **Recommended Correction:** Query `GroupMember` to ensure `user_id` is an active member of `group_id` before allowing wishlist interaction.

---

### FIND-07: Geospatial Coordinate Privacy Leak & Trilateration Vulnerability
- **File Path:** `apps/api/app/modules/search/service.py` & `apps/api/app/modules/properties/service.py`
- **Function:** `search_properties` & `_format_property_response`
- **Problem:**
  1. In `search_properties`, if any user sends an Authorization header (`is_authenticated_viewer = True`), exact un-fuzzed coordinates are returned for all listings.
  2. In `GET /properties/{id}`, exact building address (`address_exact`) and exact coordinates are exposed to anyone.
  3. `distance_km` in search results is computed with high precision against the exact coordinates, enabling trilateration attacks to recover the true location.
- **Severity:** **HIGH**
- **Evidence:** Lines 96–100 of `search/service.py`:
  ```python
  if is_authenticated_viewer:
      fuzzed_lat, fuzzed_lng = lat, lng
      is_fuzzed = False
  else:
      fuzzed_lat, fuzzed_lng = fuzz_coordinates(lat, lng, precision_decimals=2)
  ```
- **Recommended Correction:** Restrict exact coordinates and `address_exact` exclusively to the property owner, confirmed viewing appointment holders, or accepted applicants. Unconfirmed seekers must only receive fuzzed locality coordinates and masked street addresses.

---

### FIND-08: Plaintext Disclosure of Private Lifestyle Traits in Explanations
- **File Path:** `apps/api/app/modules/matching/engine.py`
- **Function:** Compatibility scoring functions (lines 44, 50, 99, 155, 159, 160)
- **Problem:** Human-readable explanation strings directly embed the target user's private categorical responses (e.g., `Cleanliness expectations (5/5 vs 1/5)`, `Dietary compatibility (pure_veg & non_veg)`).
- **Severity:** **MEDIUM**
- **Evidence:** Explanation templates construct strings containing `{c2}`, `{d2}`, `{w2}`.
- **Recommended Correction:** Rephrase explanation strings to describe alignment objectively (e.g., "Cleanliness preferences are closely aligned" or "Contrasting cleanliness habits detected") without disclosing the counterpart's exact survey answers.

---

### FIND-09: Unsafe Default JWT Secret & Missing JWKS Validation
- **File Path:** `apps/api/app/core/config.py` & `security.py`
- **Function:** `decode_token`
- **Problem:** `Settings` defines a hardcoded default `SECRET_KEY` (`supersecretkey_please_change...`). When `SUPABASE_JWT_SECRET` is unset or fails, `decode_token` falls back to this hardcoded key. Furthermore, the application only supports `HS256` HMAC signing, lacking JWKS or `RS256` asymmetric verification for standard modern Supabase Auth setups.
- **Severity:** **HIGH**
- **Evidence:** `apps/api/app/core/config.py` lines 10–11 and `security.py` lines 80–99.
- **Recommended Correction:** Enforce that in `production` and `staging`, `SUPABASE_JWT_SECRET` or a strong `SECRET_KEY` must be explicitly provided (fail startup if default key is used). Support asymmetric RS256/JWKS validation.

---

### FIND-10: Disconnected Storage Infrastructure
- **File Path:** `apps/api/app/infrastructure/storage.py`
- **Function:** `StorageProvider`, `LocalStorageProvider`, `SupabaseStorageProvider`
- **Problem:** The storage provider is never called anywhere in the application router or services. File upload endpoints do not exist; document verification and property images rely entirely on client-supplied string URLs without backend file validation, MIME verification, or signed URL generation.
- **Severity:** **MEDIUM**
- **Evidence:** Zero occurrences of `get_storage` or `upload_file` across `apps/api/app/modules/`.
- **Recommended Correction:** Add dedicated upload and presigned URL endpoints for verification documents and property images with strict file type (PNG, JPEG, PDF) and size (<= 5MB) validation.

---

### FIND-11: Missing Row-Level Locking on Bed Occupancy Updates
- **File Path:** `apps/api/app/modules/properties/service.py`
- **Function:** `assign_bed_occupant` (lines 281–309)
- **Problem:** `assign_bed_occupant` queries `Bed` using a standard `select()` without `.with_for_update()`. Under concurrent requests, two users could be assigned to the same bed simultaneously, violating ADR-004's claim that `SELECT ... FOR UPDATE` was implemented.
- **Severity:** **HIGH**
- **Evidence:** `query = select(Bed).options(...).where(Bed.id == bed_id)` lacks `.with_for_update()`.
- **Recommended Correction:** Add `.with_for_update()` to the bed and room selection queries within the transaction.

---

### FIND-12: Ineffective Row-Level Security Configuration
- **File Path:** `database/policies/rls_policies.sql`
- **Module:** PostgreSQL RLS
- **Problem:** RLS policies filter rows using `NULLIF(current_setting('app.current_user_id', true), '')::UUID`. However, the SQLAlchemy connection pool connects as a single database superuser/application user (`postgres`) and never issues `SET LOCAL app.current_user_id = :user_id`. Consequently, RLS is either bypassed (when superuser) or blocks all rows (when non-superuser).
- **Severity:** **HIGH**
- **Evidence:** Search across `apps/api/app` shows zero calls to `set_config` or `app.current_user_id`.
- **Recommended Correction:** Provide a session hook or middleware that executes `SET LOCAL app.current_user_id = :uid` for authenticated database sessions, or ensure application-layer authorization checks are strictly bulletproof.

---

### FIND-13: Handcrafted Synthetic 64-Dimensional Vectors
- **File Path:** `apps/api/app/modules/lifestyle/service.py` & `infrastructure/external_services/semantic_search.py`
- **Function:** `compute_lifestyle_profile_vector`, `generate_embedding`
- **Problem:** The 64-dimensional vectors stored in pgvector columns are generated via trigonometric functions (`math.cos(i * 0.785)`) on survey answers, and MD5 hashing of tokens modulo 64. These are pseudo-embeddings that do not reflect any real transformer/neural model. Furthermore, modern embedding models operate at 384, 512, 768, or 1536 dimensions, making this `vector(64)` column incompatible with future real embedding models.
- **Severity:** **MEDIUM**
- **Evidence:** `apps/api/app/modules/lifestyle/service.py` lines 15–85 and `semantic_search.py` lines 66–82.
- **Recommended Correction:** Document clearly that current vector columns store deterministic heuristic encodings. For future AI migration, plan a schema migration to standard 384-dim (e.g., all-MiniLM-L6-v2) or 1536-dim vectors.

---

### FIND-14: API Specification Discrepancies
- **File Path:** `API_SPECIFICATION.md` vs FastAPI OpenAPI schema
- **Problem:**
  - `GET /api/v1/domains/` and `/professions` documented in spec but not implemented in FastAPI router.
  - `GET /api/v1/users/me/roles` documented in spec, but implemented only under `/admin/users/{user_id}/roles`.
  - `DELETE /api/v1/properties/{id}` documented in spec, but implemented as `PATCH /properties/{id}/status`.
  - `GET /api/v1/rooms/{id}` documented in spec, but rooms are accessed via property endpoints.
  - `GET /api/v1/pg/facilities` documented in spec, but implemented as `GET /api/v1/pg/buildings`.
- **Severity:** **MEDIUM**
- **Evidence:** Comparison between `API_SPECIFICATION.md` and registered routes in `apps/api/app/api/v1/router.py`.
- **Recommended Correction:** Synchronize `API_SPECIFICATION.md` and OpenAPI documentation with the implemented routes.

---

### FIND-15: Drift in Shared TypeScript Contracts (`@flatmate/contracts`)
- **File Path:** `packages/contracts/src/property.ts` & `matching.ts`
- **Module:** TypeScript Contracts Package
- **Problem:** `@flatmate/contracts` contains Phase 0 prototypes (`property_type`, `deposit`, `address`) instead of Phase 5+ relational schemas (`property_category`, `configuration`, `address_display`, `address_exact`, `security_deposit`, `currency`, `max_capacity`, `current_occupants`, `beds`). `ScoreBreakdown` is missing `factors`, `explanations`, `conflicts`, and `algorithm_version`.
- **Severity:** **HIGH**
- **Evidence:** `packages/contracts/src/property.ts` lines 16–43 and `matching.ts` lines 4–13.
- **Recommended Correction:** Align `@flatmate/contracts` types directly with the Pydantic v2 schemas from `apps/api/app/modules/*/schemas.py`.

---

## 4. Audit Checklist Assessment (14 Inspection Points)

1. **Are all documented modules implemented?**  
   *Partial.* `professional_domains`, `subscriptions`, and `locations` exist only as SQLAlchemy models without routers or services. `storage` and `external_services` exist as utility classes but are not wired into the application routes.
2. **Are API endpoints genuinely functional?**  
   *Yes, for implemented modules*, though several endpoints exhibit authorization bypasses or unhandled query edge cases.
3. **Are any endpoints placeholders?**  
   *Yes.* `auth/otp/send` and `verify` are mock endpoints. `auth/logout` is a static message without token invalidation. Storage uploads are simulated by client-provided strings.
4. **Are database models actually connected to application services?**  
   *Core models are connected.* `ProfessionalDomain`, `SubscriptionPlan`, `Payment`, and `Locality` models are registered in metadata but disconnected from API services.
5. **Are transactions implemented correctly?**  
   *Partially.* Basic rollback exists, but row-level locks (`SELECT ... FOR UPDATE`) are missing on concurrent room/bed occupancy updates and rental applications.
6. **Are migrations complete and reproducible?**  
   *No.* Alembic `versions/` folder is empty. Raw SQL migrations in `database/migrations/` have column mismatches with SQLAlchemy models for `properties`.
7. **Are authorization checks applied consistently?**  
   *No.* Critical BOLA/IDOR holes identified in `applications/{id}`, `appointments/{id}`, and `groups/{id}/members`.
8. **Are RLS policies present and effective?**  
   *Present in SQL, but ineffective* because application connection pool does not set `app.current_user_id` session setting.
9. **Are there unused or duplicated modules?**  
   *Yes.* `apps/api/app/infrastructure/geo.py` duplicates `geospatial.py`. `external_services` wrappers are unused.
10. **Are there circular dependencies?**  
    *None detected.* All Python modules import cleanly.
11. **Are there hardcoded secrets or unsafe defaults?**  
    *Yes.* Insecure default `SECRET_KEY`, `DEBUG=True` default, and fallback decoding logic in `security.py`.
12. **Are there incomplete TODOs or unimplemented methods?**  
    *No explicit TODO comments*, but documented domain endpoints and storage handling are unimplemented.
13. **Does the API specification match the real OpenAPI schema?**  
    *No.* Mismatches across multiple paths, HTTP verbs, and parameters.
14. **Does the frontend integration guide match actual API contracts?**  
    *No.* Guide specifies incorrect HTTP methods (`GET` instead of `POST` for search) and points to non-existent endpoints.

---

## 5. Audit Verdict & Next Actions

- **Current Status:** **BLOCKED / NOT READY** until Critical and High severity findings are remediated.
- **Immediate Requirement:** Proceed to **Step 2 (Fresh Test Execution)** and document baseline test outputs before executing targeted fixes in subsequent steps.
