# PHASE 17 — FRONTEND–BACKEND INTEGRATION AUDIT

**Project:** Flatmate Compatibility & Rental Marketplace  
**Phase:** Phase 17 — Frontend–Backend Integration  
**Date:** November 13, 2026  
**Auditor:** Antigravity AI Engine  
**Previous Phase Status:** Phase 16 — CONDITIONALLY READY (84/84 Backend Unit/Regression/Sync Tests Passing)  

---

## 1. Executive Summary

This comprehensive audit inspects the monorepo architecture, comparing the Next.js 14 frontend (`apps/web`), the shared contract types (`packages/contracts`), the UI component library (`packages/ui`), and the FastAPI backend (`apps/api`) with 20 modular routers.

The objective of Phase 17 is to transition the frontend from standalone UI mockups and static stubs to a fully integrated, production-grade web client communicating with real backend endpoints, real PostgreSQL schemas, real JWT authentication, and strict compliance with the project's **Real Data Policy**.

---

## 2. Monorepo & Frontend Architecture

### 2.1 Workspace Structure
* **`apps/web`**: Next.js 14 (App Router) + TypeScript + TailwindCSS + `@flatmate/ui` + `@flatmate/contracts`.
* **`apps/api`**: FastAPI 0.111.0 + SQLAlchemy 2.0 (asyncpg) + PostGIS + pgvector (1536-D and 64-D vectors) + Celery/Redis.
* **`packages/contracts`**: Shared TypeScript interfaces, DTOs, and API request/response types.
* **`packages/ui`**: Atomic Tailwind-styled React components (`Button`, `Card`, `Input`, `Modal`, `Avatar`, `Badge`, `MatchScoreBadge`).
* **`packages/config`**: Base TypeScript and Tailwind configurations.

### 2.2 Existing Routes and Screens
| Route | Type | Description | Current Integration State |
|---|---|---|---|
| `/` | Page | Landing Page (Hero, How it works, Featured) | **MOCK DATA**: Uses hardcoded `FEATURED_PROPERTIES` & `FEATURED_FLATMATES`. |
| `/login` | Page | User Sign In | **PARTIAL**: Calls `/auth/login`, stores token in `localStorage`. |
| `/register` | Page | User Registration | **PARTIAL**: Calls `/auth/register` with role toggle. |
| `/dashboard` | Page | Seeker Dashboard & Quiz Form | **PARTIAL**: Calls `/applications/me` and `/profiles/me`. Quiz form incomplete; Trust score hardcoded (95/100). |
| `/properties` | Page | Property Directory & Filter | **INTEGRATED**: Calls `GET /properties` with query params. |
| `/properties/[id]` | Dynamic | Property & Room Detail, Apply Modal | **PARTIAL**: Calls `GET /properties/{id}` and `POST /applications`. Field naming inconsistencies with backend response. |
| `/flatmates` | Page | Seeker Directory & Filters | **FLAWED**: Calls `GET /flatmates/search` without auth check; hardcodes `matchScore={92}` on cards. |
| `/flatmates/[id]` | Dynamic | Seeker Profile & Compatibility Radar | **MOCK DATA**: Calls `GET /profiles/{id}`, but falls back to hardcoded mock compatibility score when unauthenticated. |
| `/matches` | Page | AI Vector Recommendations | **PARTIAL**: Calls `GET /matching/recommendations`. Does not support interactions (like, save, pass). |
| `/groups` | Page | Flatmate Hunting Syndicates | **BROKEN CALL**: Calls `POST /groups/{id}/members` without required body payload. Missing wishlist voting UI. |
| `/messages` | Page | Chat Threads & WebSocket stream | **INTEGRATED**: Connects to `GET /messaging/conversations`, `GET /messaging/conversations/{id}/messages`, `POST /messaging/messages`, and WS `/messaging/ws`. |

---

## 3. Backend Endpoint Availability & Coverage

All 20 backend routers are mounted under `/api/v1`:

1. **Authentication (`/auth`)**:
   * `POST /auth/register` — Available
   * `POST /auth/login` — Available
   * `POST /auth/refresh` — Available
   * `POST /auth/otp/send` — Available
   * `POST /auth/otp/verify` — Available
   * `GET /auth/me` — Available
   * `POST /auth/logout` — Available
2. **Users (`/users`)**:
   * `GET /users/me`, `PUT /users/me`, `GET /users/{user_id}` — Available
3. **Profiles (`/profiles`)**:
   * `GET /profiles/me`, `PUT /profiles/me`, `POST /profiles/me/quiz`, `GET /profiles/{user_id}` — Available
   * `GET /profiles/me/privacy`, `PUT /profiles/me/privacy` — Available
4. **Lifestyle & Dealbreakers (`/lifestyle`)**:
   * `GET /lifestyle/me`, `PUT /lifestyle/me` — Available
   * `GET /lifestyle/dealbreakers`, `POST /lifestyle/dealbreakers`, `DELETE /lifestyle/dealbreakers/{id}` — Available
   * `GET /lifestyle/{user_id}` — Available
5. **Properties (`/properties`)**:
   * `GET /properties/`, `POST /properties/`, `GET /properties/{id}`, `PUT /properties/{id}`, `PATCH /properties/{id}/status` — Available
   * `POST /properties/beds/{id}/assign`, `POST /properties/beds/{id}/vacate` — Available
6. **Search & Geospatial (`/search`)**:
   * `POST /search/properties`, `POST /search/flatmates` — Available
7. **Flatmates (`/flatmates`)**:
   * `GET /flatmates/search` — Available (Requires authenticated user)
8. **Matching Engine (`/matching`)**:
   * `GET /matching/recommendations`, `GET /matching/compatibility/{target_user_id}`, `POST /matching/interactions`, `GET /matching/matches` — Available
9. **Groups & Syndicates (`/groups`)**:
   * `GET /groups/`, `POST /groups/`, `GET /groups/{id}`, `POST /groups/{id}/members`, `DELETE /groups/{id}/members/{user_id}`, `GET /groups/{id}/compatibility`, `POST /groups/{id}/wishlist/{property_id}/vote` — Available
10. **Applications (`/applications`)**:
    * `GET /applications/me`, `POST /applications/`, `GET /applications/{id}`, `PATCH /applications/{id}/status` — Available
11. **Appointments (`/appointments`)**:
    * `GET /appointments/`, `POST /appointments/`, `GET /appointments/{id}`, `PATCH /appointments/{id}/status` — Available
12. **Owners (`/owners`)**:
    * `GET /owners/dashboard`, `GET /owners/applications`, `GET /owners/properties/{id}/tenants` — Available
13. **Tenants (`/tenants`)**:
    * `GET /tenants/my-memberships`, `POST /tenants/vacancies`, `GET /tenants/vacancies`, `GET /tenants/vacancies/{id}`, `DELETE /tenants/vacancies/{id}` — Available
14. **PG Management (`/pg`)**:
    * `POST /pg/buildings`, `GET /pg/buildings`, `GET /pg/buildings/{id}`, `POST /pg/buildings/{id}/floors` — Available
15. **Messaging (`/messaging`)**:
    * `GET /messaging/conversations`, `POST /messaging/conversations`, `GET /messaging/conversations/{id}/messages`, `POST /messaging/messages`, `WS /messaging/ws` — Available
16. **Notifications (`/notifications`)**:
    * `GET /notifications/`, `PATCH /notifications/{id}/read` — Available
17. **Verification & Trust (`/verification`)**:
    * `POST /verification/submit`, `GET /verification/status`, `PATCH /verification/admin/approve/{id}` — Available
18. **Moderation & Safety (`/moderation`)**:
    * `POST /moderation/reports`, `GET /moderation/reports`, `PATCH /moderation/reports/{id}`, `POST /moderation/blocks/{id}`, `DELETE /moderation/blocks/{id}`, `GET /moderation/blocks` — Available
19. **Administration (`/admin`)**:
    * `GET /admin/users`, `PATCH /admin/users/{id}/status`, `POST /admin/users/{id}/roles`, `GET /admin/stats` — Available
20. **System Health (`/health`, `/ready`)**:
    * `GET /health`, `GET /health/live`, `GET /health/ready`, `GET /ready` — Available

---

## 4. Contract Mismatches & Typing Gaps

1. **`PropertyDTO` vs `PropertyResponse`**:
   * Backend returns `address_display` and `address_exact`. In `PropertyDTO`, `address` was marked as mandatory. In components (`PropertyCard.tsx`, `properties/[id]/page.tsx`), calling `property.address` returns `undefined` for real API responses.
   * Backend returns `security_deposit` and `maintenance_monthly`. Frontend contracts had `deposit`.
   * Backend property response includes `currency` (default "INR"), while `utils.ts` formatCurrency was hardcoded to "USD".
2. **`ScoreBreakdown` vs `ScoreBreakdownSchema`**:
   * Backend returns `factors: Dict[str, int]` (10 dimensions) and `explanations: Dict[str, str]`, whereas the old frontend contract expected flat fields `cleanliness_alignment`, `schedule_alignment`, etc.
   * `CompatibilityRadar` and `CompatibilityBreakdown` need normalized adapters so they render both the 10-dimension factors and legacy keys smoothly.
3. **`GroupResponse` vs `GroupDTO`**:
   * Backend returns `wishlist_items: List[GroupWishlistItemResponse]`, whereas `GroupDTO` defined `wishlist?: GroupWishlistItemDTO[]`.
   * `AddMemberRequest` in backend requires `{ user_id: UUID, role?: string }`, but frontend `handleJoinGroup` sent an empty POST request.
4. **Token Handling**:
   * Backend returns `TokenResponse` with `access_token`, `refresh_token`, `token_type`, `expires_in`, `user`, and `roles: List[str]`.
   * Frontend `TokenResponse` in contracts needs alignment with `roles`.

---

## 5. Authentication & Security Gaps

1. **Missing Token Expiration & Refresh Flow**:
   * The existing `api-client.ts` reads `flatmate_access_token` from `localStorage`, but never attempts silent refresh on 401 using `/auth/refresh`.
2. **Missing RFC 7807 Error Parsing**:
   * Existing `apiClient` assumes `errorBody.detail` or `errorBody.message`. When backend returns RFC 7807 `application/problem+json` (`{ type, title, status, detail, error_code, invalid_params }`), the error details are not exposed in a typed manner.
3. **Protected Endpoint Guards in Frontend**:
   * Unauthenticated users clicking on `/flatmates` trigger `GET /flatmates/search`, which throws 401 Unauthorized because the backend endpoint requires an authenticated seeker.
   * A clean fallback/login prompt or public preview must be rendered.
4. **Exact Residential Coordinate Masking**:
   * Backend masks `address_exact` to `[Exact address protected - revealed upon confirmed visit]` for non-owners/non-admins. Frontend must properly display this privacy protection and explain it to users.

---

## 6. Mock Data & Non-Functional Controls Inventory

1. **`apps/web/app/page.tsx`**:
   * `FEATURED_PROPERTIES` mock array (hardcoded San Francisco properties).
   * `FEATURED_FLATMATES` mock array (hardcoded users).
   * Stats counters ("94%", "12k+", "0 Fraud") hardcoded.
2. **`apps/web/app/flatmates/page.tsx`**:
   * Hardcoded `matchScore={92}` passed to `FlatmateCard`.
3. **`apps/web/app/flatmates/[id]/page.tsx`**:
   * Hardcoded `displayScore` fallback with dummy 94% score.
   * "Invite to Group" button was a non-functional dead button.
4. **`apps/web/app/dashboard/page.tsx`**:
   * Hardcoded trust score ("Trust & Verification Score: 95/100").
   * Missing profile info edit form.
   * Missing appointment management.
   * Missing dealbreaker configuration.
5. **Missing Screens**:
   * Owner Property Management & Listing creation screen.
   * Appointments / Viewing scheduler modal on property detail.
   * Verification document submission modal.
   * User reporting & safety modal.
   * Mutual matches & interactions list.

---

## 7. Integration Risks

1. **Live Supabase Credentials**:
   * Live Supabase production credentials are not provided in this environment. As required by Section 3, all integrations must be implemented against the verified OpenAPI contracts, and live authentication against a remote Supabase instance will be reported as BLOCKED while local JWT verification is fully tested.
2. **Geospatial & Coordinates**:
   * PostGIS coordinates are centered on Indian metros (e.g., Bengaluru: 12.9716, 77.5946). Frontend mock addresses reference US cities (SF). All frontend UI must align with Indian rental contexts (INR, configurations like 1RK/2BHK, cities like Bengaluru/Mumbai/Delhi).
3. **State Management & Stale Tokens**:
   * `localStorage` access across SSR and hydration must be guarded (`typeof window !== 'undefined'`) to prevent Next.js hydration mismatches.

---

## 8. Implementation Sequence

1. **Step 1: Contract Synchronization**:
   * Update `@flatmate/contracts` to ensure full parity with FastAPI OpenAPI schemas (`PropertyResponse`, `ScoreBreakdownSchema`, `GroupResponse`, `TokenResponse`, `AppointmentResponse`, `VerificationResponse`, `PGBuildingResponse`, etc.).
2. **Step 2: Centralized API Client & Auth Hardening**:
   * Implement enhanced `apiClient` in `apps/web/lib/api-client.ts` with RFC 7807 support, timeout/abort signals, automatic Authorization headers, silent token refresh, and safe error representations.
   * Enhance `useAuth` hook with session expiration, token refresh, and logout broadcast.
3. **Step 3: Real Feature Integrations**:
   * A. Auth & Session Management (Login, Register, Logout, Token storage).
   * B. Profile & Privacy Management (View, Edit Profile, Update Privacy Settings).
   * C. Lifestyle Questionnaire & Dealbreakers (10-dimension questionnaire & dealbreaker rules).
   * D & E. Property Discovery & Details (Geospatial search, real listing fetch, room/bed inventory, viewing appointments).
   * F & G. Flatmate Matching & Interactions (Real vector matches, compatibility breakdown, like/save/pass/block actions).
   * H. Group Workflows (Group creation, member join/leave, property wishlist voting, group compatibility).
   * I & J & K. Owner, Tenant Vacancy & PG Operations (Property listing form, tenant vacancy creation, PG management).
   * L. Applications & Appointments (Tenancy application submit, landlord review, visit booking).
   * M. Messaging & Notifications (Realtime messaging, notifications list & mark-as-read).
   * N. Safety, Trust & Verification (Verification badge status, user reporting modal, block management).
   * O. Landing Page & Dashboards (Removal of all mock data; real dynamic data fetch with responsive empty states).
4. **Step 4: Automated Testing**:
   * Frontend automated integration test suite using `node:test` covering API client, auth flow, RFC 7807 error handling, and component rendering.
   * Full Next.js production build (`next build`), lint (`next lint`), and TypeScript type checking (`tsc --noEmit`).
   * Backend regression test execution (`pytest`).
5. **Step 5: Documentation & Integration Matrices**:
   * `docs/FRONTEND_INTEGRATION_STATUS.md`
   * `docs/API_INTEGRATION_MATRIX.md`
   * `docs/PHASE_17_TEST_REPORT.md`
   * `FRONTEND_INTEGRATION_GUIDE.md`
