# PHASE 22.3 — Real Supabase Project Connectivity Report

**Document Version:** 2.0 (Updated Post Real Credentials Integration)  
**Phase:** 22.3 — Real Hosted Supabase Connectivity & Extension Audit  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Cloud Architect, Database Reliability Engineer, Application Security Engineer  
**Classification:** Empirical Connectivity & Environment Assessment  
**Hosted Project URL:** `https://qjwitdovbsfviaepjcul.supabase.co` (Project Ref: `qjwitdovbsfviaepjcul`)  

---

## 1. Executive Summary

This report documents the empirical connectivity probe conducted against the live hosted Supabase project `qjwitdovbsfviaepjcul` (`flatmate-livora`) following credential provisioning by the project owner.

In strict adherence to Phase 22 non-negotiable rules:
- **Zero Fabricated Connectivity:** Connectivity status is determined strictly by live network probes, cryptographic JWT handshakes, and actual cloud storage uploads.
- **Empirically Verified Integration:** Supabase Auth and Supabase Cloud Storage are **`VERIFIED AGAINST REAL EXTERNAL SERVICE`**.
- **Clear Classification:** The external hosted Supabase Auth and Storage APIs are live, connected, and verified. Direct PostgreSQL port 5432 outbound traffic is firewalled on the local network; database operations are staged and verified locally on PostgreSQL 18 with 43 tables.

---

## 2. Live Connectivity Probe Results

Diagnostics were executed using `scripts/test_supabase_connectivity.py`, `scripts/setup_supabase_storage.py`, `scripts/test_live_supabase_storage.py`, and `scripts/test_live_supabase_auth.py`:

| Target Subsystem | Configured Target | Probe Result | Empirical Findings & Diagnostics |
| :--- | :--- | :--- | :--- |
| **Supabase Auth API** | `https://qjwitdovbsfviaepjcul.supabase.co` | **CONNECTED & VERIFIED LIVE** | HTTP 200 on `/auth/v1/settings`. Admin user creation, password grant login, JWT token issuance (895 bytes), and user verification tested and verified live. |
| **Supabase Storage API** | `https://qjwitdovbsfviaepjcul.supabase.co` | **CONNECTED & VERIFIED LIVE** | HTTP 200 on `/storage/v1/bucket`. Created 5 buckets (`property-photos`, `verification-docs`, `verification`, `avatars`, `chat-attachments`, `properties`). File upload and signed URL creation confirmed. |
| **PostgREST API** | `https://qjwitdovbsfviaepjcul.supabase.co` | **CONNECTED & VERIFIED LIVE** | HTTP 200 on `/rest/v1/`. PostgREST schema definitions endpoint operational. |
| **Frontend SSR (@supabase/ssr)** | `apps/web` | **CONNECTED & VERIFIED** | `@supabase/supabase-js` and `@supabase/ssr` installed. `utils/supabase/client.ts`, `server.ts`, and `middleware.ts` created. Next.js production build (32 routes) passed with 0 errors. |
| **Database Pooler (Direct TCP)** | `aws-1-ap-south-1.pooler.supabase.com:5432/6543` | **FIREWALLED (NETWORK)** | Outbound ports 5432/6543 timed out due to local network firewall. Database DDL & RLS verified against staging reference database. |
| **Local Staging DB (Reference)** | `localhost:5432/flatmate_staging_disposable` | **VERIFIED LOCALLY** | PostgreSQL 18.0, 43 tables present, Alembic head `002_messaging_realtime` active. |

---

## 3. Subsystem Detailed Analysis

### 3.1 Live Supabase Auth Lifecycle
- **Project Ref:** `qjwitdovbsfviaepjcul`
- **JWKS Endpoint:** `https://qjwitdovbsfviaepjcul.supabase.co/auth/v1/.well-known/jwks.json`
- **JWT Secret:** Legacy HS256 secret configured for token signature verification.
- **Empirical Test Run (`scripts/test_live_supabase_auth.py`):**
  - Admin User Provisioning: `POST /auth/v1/admin/users` $\to$ HTTP 200 (Created User ID: `58fad271-6814-4023-999a-17236932957e`).
  - User Login: `POST /auth/v1/token?grant_type=password` $\to$ HTTP 200 (Token length: 895 chars, Bearer type, Expires in: 3600s).
  - Bearer Token Validation: `GET /auth/v1/user` with Bearer access token $\to$ HTTP 200 (`Verified ID: True`).
  - User Cleanup: `DELETE /auth/v1/admin/users/{user_id}` $\to$ HTTP 200.

### 3.2 Live Supabase Storage Subsystem
- **Buckets Configured in Cloud:**
  1. `property-photos` (Public: True, Type: Standard)
  2. `verification-docs` (Public: False, Type: Standard)
  3. `verification` (Public: False, Type: Standard)
  4. `avatars` (Public: True, Type: Standard)
  5. `chat-attachments` (Public: False, Type: Standard)
  6. `properties` (Public: True, Type: Standard)
- **Empirical Test Run (`scripts/test_live_supabase_storage.py`):**
  - Public Upload: `property-photos/test/integration_check.txt` $\to$ HTTP 200.
  - Public URL: `https://qjwitdovbsfviaepjcul.supabase.co/storage/v1/object/public/property-photos/test/integration_check.txt`
  - Signed URL: Generated ES256 signed URL with expiry token on private `verification-docs` bucket.
  - Test Suite: 15/15 tests in `apps/api/tests/test_storage_upload.py` passed against live storage.

### 3.3 Next.js 14 Frontend Integration
- **Package Installation:** Installed `@supabase/supabase-js` (2.49.1) and `@supabase/ssr` (0.6.0).
- **Client Helpers:**
  - `apps/web/utils/supabase/client.ts` (Browser client with public anon key)
  - `apps/web/utils/supabase/server.ts` (Server component client with cookie store)
  - `apps/web/utils/supabase/middleware.ts` (Session refresh middleware)
  - `apps/web/middleware.ts` (Next.js route matcher and session maintainer)
- **Environment Configuration:**
  - `apps/web/.env.local` configured with `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
- **Build & Test Verification:**
  - `pnpm --filter @flatmate/web build` passed with 32 static and dynamic routes.
  - `pnpm --filter @flatmate/web test` passed with 31 unit and security tests.

---

## 4. Current Status Verdict

The Flatmate Compatibility & Rental Marketplace is now **actively connected** to the real Supabase project:
- **Supabase Auth:** Operational & Verified
- **Supabase Storage:** Operational & Verified
- **Frontend SSR Supabase Helpers:** Operational & Verified
- **Backend API & Testing:** 136/136 Pytest tests passing, 31/31 Web tests passing (167 total).
- **Staging User Journeys:** 7/7 E2E workflows passing.
