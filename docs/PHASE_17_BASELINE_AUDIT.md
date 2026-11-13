# Phase 17 Baseline Audit & Repository Discovery
## Flatmate Compatibility & Rental Marketplace

**Document Version:** 1.0  
**Phase:** Phase 17 — Complete Frontend–Backend Integration  
**Date:** 2026-11-13  
**Status:** BASELINE ESTABLISHED  

---

## 1. Executive Summary

In accordance with Phase 17 Step 0 instructions, an independent discovery and baseline audit of the monorepo was conducted. The baseline was established by inspecting the repository architecture, running all primary test, lint, and build suites across backend and frontend, and categorizing all findings without concealing pre-existing defects.

### Key Baseline Metrics
- **Backend Unit & E2E Tests:** `84 passed` in 4.93s (`python -m pytest apps/api/tests -q`).
- **Backend Type Checking:** `python -m mypy apps/api/app` failed with exit code 1 (`Duplicate module named 'router'`) due to missing `__init__.py` markers across namespace packages. When package bases are mapped (`MYPYPATH=apps/api; python -m mypy -p app`), 18 typing errors were discovered across 9 files (auth, pg_management, messaging, profiles, groups).
- **Backend Linter:** `python -m ruff check apps/api` returned exit code 1 with 38 violations (33 unused imports, 5 unused local variables).
- **Frontend Monorepo Tests (`pnpm turbo run test --force`):** 4/4 tasks succeeded (tsc on `@flatmate/contracts`, `@flatmate/ui`, and `@flatmate/web`).
- **Frontend Linter (`pnpm turbo run lint --force`):** Succeeded with 0 warnings or errors.
- **Frontend Build (`pnpm turbo run build --force`):** FAILED with exit code 1 (`Type error: Argument of type 'number | undefined' is not assignable to parameter of type 'string | number'` in `apps/web/app/properties/[id]/page.tsx:229:42`).
- **Frontend Dependencies (`pnpm install`):** Clean and up to date in 2.2s.

---

## 2. Command Execution Record

| Command | Working Dir | Exit Code | Tests / Files | Result | Duration | Notes / Issues |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `pnpm install` | Monorepo root | 0 | 5 projects | Success | 2.2s | Lockfile up to date |
| `pnpm turbo run test --force` | Monorepo root | 0 | 4 packages | 4/4 Passed | 42.7s | Typecheck passed |
| `pnpm turbo run lint --force` | Monorepo root | 0 | 1 package | 0 errors | 6.7s | ESLint clean |
| `pnpm turbo run build --force` | Monorepo root | 1 | `@flatmate/web` | Failed | 22.1s | TS error: `property.deposit` undefined |
| `python -m pytest apps/api/tests -q` | `apps/api` | 0 | 84 passed | 84/84 Passed | 4.93s | Core backend suites pass |
| `python -m mypy apps/api/app` | `apps/api` | 1 | 1 error | Duplicate router | 1.8s | Package root discovery issue |
| `python -m mypy -p app` (MYPYPATH=apps/api) | `apps/api` | 1 | 126 source files | 18 errors in 9 files | 3.5s | 4 untyped imports, 14 type mismatches |
| `python -m ruff check apps/api` | `apps/api` | 1 | All python files | 38 errors | 0.3s | 33 unused imports, 5 unused variables |

---

## 3. Frontend Audit Findings

### 3.1 Route Inventory & Status
| Route | File Path | Current Status | Issues & Gaps |
| :--- | :--- | :---: | :--- |
| `/` | `apps/web/app/page.tsx` | Partial | Uses hardcoded San Francisco mock properties & seekers; not India-first live data. |
| `/(auth)/login` | `apps/web/app/(auth)/login/page.tsx` | Functional | Connects to `/auth/login`; missing password reset flow and advanced token refresh. |
| `/(auth)/register` | `apps/web/app/(auth)/register/page.tsx` | Functional | Connects to `/auth/register`; needs terms acceptance and password validation. |
| `/dashboard` | `apps/web/app/dashboard/page.tsx` | Broken endpoint | Applications load (`/applications/me`), but quiz saving calls nonexistent `/profiles/me/quiz` instead of `PUT /lifestyle/me`. |
| `/properties` | `apps/web/app/properties/page.tsx` | Partial | Fetches `/properties`, but lacks filter dimensions (configuration, furnishing, category, verified status) and pagination. |
| `/properties/[id]` | `apps/web/app/properties/[id]/page.tsx` | Broken Build | TypeScript error on line 229 (`property.deposit`). Lacks enquiries and viewing appointments integration. |
| `/flatmates` | `apps/web/app/flatmates/page.tsx` | Functional | Fetches `/flatmates/search`. Needs unauthenticated state handling and expanded India filters. |
| `/flatmates/[id]` | `apps/web/app/flatmates/[id]/page.tsx` | Rule 2.1 Violation | Injects hardcoded mock score (94%) when unauthenticated. Must only show real backend score or prompt login. |
| `/matches` | `apps/web/app/matches/page.tsx` | Partial | Displays recommendations; lacks Like/Pass interaction actions and mutual match list view. |
| `/groups` | `apps/web/app/groups/page.tsx` | Broken Handler | "Join Group" POSTs to `/groups/{id}/members` without user ID or payload. Missing group compatibility and wishlist voting UI. |
| `/messages` | `apps/web/app/messages/page.tsx` | Functional | Realtime WebSocket + REST history. Needs connection resiliency and user search/initiation. |

### 3.2 Unintegrated Frontend Components
The following reusable feature components were built in Phase 16 but not integrated into the main route hierarchy:
1. `apps/web/features/matching/components/CompatibilityBreakdown.tsx`: Complete 10D score visualizer.
2. `apps/web/features/matching/components/DealbreakerAlert.tsx`: Strict dealbreaker banner.
3. `apps/web/features/groups/components/GroupWishlistCard.tsx`: Group wishlist voting card.
4. `apps/web/features/properties/components/PropertyInventoryForm.tsx`: Indian rental listing inventory form with units, rooms, and beds.
5. `apps/web/features/messaging/components/ChatWindow.tsx`: Interactive chat with safety checks.

### 3.3 Missing Frontend Modules
1. **Password Recovery:** `/forgot-password` and `/reset-password`.
2. **Profile & Lifestyle Questionnaire:** Dedicated 10-dimension onboarding/edit route (`/profile` or `/onboarding`).
3. **Owner Listing Management:** `/owner/listings/create` and `/owner/dashboard`.
4. **Existing Tenant Vacancy:** `/tenants/vacancies/create`.
5. **PG Operator Management:** `/pg/manage`.
6. **Viewing Appointments:** `/appointments`.
7. **Trust & Moderation:** `/admin/moderation` queue and report submission modals.
8. **Storage / Uploads:** File upload component with backend upload endpoint.

---

## 4. Backend Audit Findings

1. **Missing `__init__.py` markers:** Subdirectories in `apps/api/app/modules/` lack `__init__.py`, causing mypy to fail on duplicate module names (`router.py`) unless explicit package bases are provided.
2. **Type Incompatibilities:** 18 errors identified in `apps/api/app` under strict mypy package inspection:
   - `auth/service.py`: `TokenResponse` expects `UserResponse`, received ORM `User` model.
   - `pg_management/service.py`: Return value type `PGBuilding | None` vs `PGBuilding`.
   - `messaging/service.py`: `Sequence[UUID]` passed to `broadcast_to_users` expecting `list`.
   - `profiles/service.py`: Unpacked dictionary kwargs type mismatch with `ProfileResponse`.
   - `groups/service.py`: Return value type `Group | None` vs `Group`.
3. **Storage Upload API Endpoint:** The backend has a pluggable `StorageProvider` in `apps/api/app/infrastructure/storage.py`, but lacks a dedicated FastAPI router exposing authenticated file upload endpoints (`POST /api/v1/storage/upload`) and presigned URL generation.
4. **Unused Imports & Variables in Tests:** Ruff reported 38 lint issues primarily in newly created Phase 16 test files.

---

## 5. Baseline Remediation Plan for Phase 17

1. **Step 1:** Implement robust centralized API client with automatic token refresh, RFC 7807 problem details parsing, correlation IDs, abort signals, and multipart upload support.
2. **Step 2:** Fix frontend build error in `apps/web/app/properties/[id]/page.tsx` and currency formatting in `apps/web/lib/utils.ts`.
3. **Step 3:** Add `__init__.py` across backend modules and fix the 18 mypy typing errors and 38 ruff lint issues.
4. **Step 4:** Add backend storage router (`/api/v1/storage/upload`) for authenticated property image, profile avatar, and document uploads.
5. **Step 5:** Wire all core user journeys:
   - Profile & 10D lifestyle questionnaire with dealbreakers.
   - Property search, details, and owner listing creation wizard.
   - Flatmate discovery, explainable 10D compatibility, likes, passes, and mutual matches.
   - Group creation, member invitation, wishlist voting, and group compatibility.
   - Applications, enquiries, and viewing appointments with conflict prevention.
   - Realtime messaging with safety heuristics.
   - Moderation reports, blocking, and admin queue.
6. **Step 6:** Run full test suites, E2E journeys, and performance benchmarks to ensure 100% compliance.
