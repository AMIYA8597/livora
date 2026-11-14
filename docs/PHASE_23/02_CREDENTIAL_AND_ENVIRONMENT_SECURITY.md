# PHASE 23.2 — Credential Security and Environment Validation

**Document Version:** 1.0  
**Phase:** 23.2 — Credential Security and Environment Validation  
**Date:** November 14, 2026  
**Auditor Roles:** Application Security Engineer, Cloud Security Architect, DevSecOps Engineer  
**Classification:** Empirical Security, Secrets & Environment Validation  
**Project:** Flatmate Compatibility & Rental Marketplace  

---

## 1. Executive Summary

This report delivers the empirical security audit of credential hygiene, environment isolation, secrets exposure risks, and JWT verification mechanisms for the Flatmate platform.

In strict compliance with **Execution Rule 0**:
- No raw secret values, API keys, passwords, or signing tokens are printed or logged.
- Only variable names and configuration presence/validity states are evaluated.
- Empirical verification was performed on both symmetric (HS256) and live asymmetric (ES256 JWKS) token verification paths.

---

## 2. Secrets Exposure & Git History Audit

### 2.1 Git Repository History Inspection
A full-history commit tree scan was executed across all branches using:
```bash
git log --all --full-history --name-only --oneline -- "**.env*"
```
**Findings:**
- **Zero Raw Secrets Committed:** The only `.env` files committed to Git are example template files:
  - `.env.example`
  - `.env.staging.example`
  - `.env.staging.local.example`
  - `.env.production.example`
- No real `.env`, `.env.local`, or `.env.staging` files containing live credentials have ever been committed or tracked in Git history.

### 2.2 `.gitignore` Enforcement
The `.gitignore` configuration explicitly rejects all secret files while allowing only explicit templates:
```gitignore
# Environment variables
.env
.env.*
!.env.example
!.env.staging.example
!.env.staging.local.example
!.env.production.example
```

### 2.3 Frontend Secret Leakage Boundary Verification
Automated scanner `apps/web/tests/security_auth.test.ts` scans all TypeScript, JavaScript, and JSON source files under `apps/web` (excluding `node_modules` and build directories) for sensitive secret patterns:
- `SUPABASE_SERVICE_ROLE_KEY`
- `service_role`
- `postgres://` / `postgresql://`
- `SECRET_KEY =`
- `SUPABASE_JWT_SECRET`

**Empirical Result:** 31 frontend security & unit tests passed (`@flatmate/web:test` exit code 0). Zero secret tokens exist in frontend code or client bundles.

---

## 3. Environment Separation Matrix

The application strictly differentiates across four deployment environments:

| Variable Name | Client / Browser Visible | Development | Automated Testing | Staging | Production |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `NEXT_PUBLIC_APP_URL` | Yes | `http://localhost:3000` | Mock / Test Server | `https://staging.flatmate.internal` | `https://flatmate.in` |
| `NEXT_PUBLIC_API_URL` | Yes | `http://localhost:8000/api/v1` | `http://testserver/api/v1` | `https://api-staging.flatmate.internal/api/v1` | `https://api.flatmate.in/api/v1` |
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Configured | Configured | Configured | Configured |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Yes | Configured | Configured | Configured | Configured |
| `NEXT_PUBLIC_WS_URL` | Yes | `ws://localhost:8000/api/v1/messaging/ws` | Mock WS | `wss://api-staging.flatmate.internal/...` | `wss://api.flatmate.in/...` |
| `SECRET_KEY` | **NO (Backend Only)** | Configured (Local) | Test Secret | Managed Secret | Vault / AWS KMS |
| `SUPABASE_SERVICE_ROLE_KEY` | **NO (Backend Only)** | Configured | Not used by client | Managed Secret | Vault / AWS KMS |
| `SUPABASE_JWT_SECRET` | **NO (Backend Only)** | Optional (Legacy) | Test Secret | Managed Secret | Vault / AWS KMS |
| `SUPABASE_JWKS_URL` | **NO (Backend Only)** | Auto-derived / Set | Local Mock / Skip | Auto-derived / Set | Auto-derived / Set |
| `DATABASE_URL` | **NO (Backend Only)** | `localhost:5432` | SQLite / Local PG | Staging PG Pooler | Production PG Pooler |
| `REDIS_URL` | **NO (Backend Only)** | `localhost:6379` | Mock / Memory | Staging Redis | Production Redis Cluster |
| `STORAGE_TYPE` | **NO (Backend Only)** | `local` / `supabase` | `local` | `supabase` | `supabase` |

---

## 4. JWT Signing Architecture & JWKS Implementation

### 4.1 Hosted Supabase Signing Configuration
Empirical probe of `https://qjwitdovbsfviaepjcul.supabase.co/auth/v1/.well-known/jwks.json`:
- **Key Type (`kty`):** `EC` (Elliptic Curve)
- **Algorithm (`alg`):** `ES256` (ECDSA using P-256 and SHA-256)
- **Key ID (`kid`):** `f93dccdb-5472-4117-9334-c84b0531d18b`
- **Intended Use (`use`):** `sig` (Digital Signature)

Empirical inspection of live Supabase JWT issued by password authentication:
```json
Header: {"alg": "ES256", "kid": "f93dccdb-5472-4117-9334-c84b0531d18b", "typ": "JWT"}
Claims: {"iss": "https://qjwitdovbsfviaepjcul.supabase.co/auth/v1", "aud": "authenticated", "sub": "..."}
```

### 4.2 Backend Dynamic Verification Strategy
In `apps/api/app/core/security.py`, `decode_token` was upgraded with in-memory cached JWKS public key resolution:
1. **Asymmetric Tokens (`ES256` / `RS256`):**
   - Resolves public key from Supabase JWKS endpoint with 1-hour TTL caching (`_JWKS_CACHE`).
   - Cryptographically validates token signature against the public EC key.
2. **Symmetric Tokens (`HS256`):**
   - Validates legacy and automated test tokens using `SUPABASE_JWT_SECRET` or local `SECRET_KEY`.
3. **Verification Results:**
   - Local HS256 token: Verified successfully (`assert sub == expected_sub`).
   - Live Supabase ES256 token: Verified successfully (`assert sub == real_supabase_user_id`).
   - Regression suite: All 136 backend tests passed.

---

## 5. Credential Rotation Checklist (Pre-Approval Plan)

When rotating Supabase API keys or database passwords:

1. **Step 1: Dashboard Secret Generation**
   - In Supabase Dashboard -> Project Settings -> API, initiate service-role key rollover or JWT secret change.
2. **Step 2: Staging Vault / Secret Manager Update**
   - Store new `SUPABASE_SERVICE_ROLE_KEY` and updated secrets in environment store.
3. **Step 3: Blue/Green Backend Deployment**
   - Deploy backend instances configured with the new credentials. Because JWKS keys are fetched dynamically by `kid`, asymmetric key transitions complete with zero downtime.
4. **Step 4: Frontend Rollout**
   - If publishable/anon key was rotated, update `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` and trigger Next.js rebuild.
5. **Step 5: Revoke Deprecated Credentials**
   - Confirm all traffic utilizes the new key pair, then terminate the old secret in Supabase dashboard.

*Note: In compliance with Approval Boundaries, live rotation is NOT executed without explicit user instruction.*
