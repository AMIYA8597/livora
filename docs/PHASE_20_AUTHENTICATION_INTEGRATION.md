# Phase 20 Authentication Integration Architecture

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** Application Security & Frontend Deployment Engineer  

---

## 1. Authentication Topology & Hybrid Architecture

The platform implements an enterprise hybrid authentication model:
- **Supabase Auth Gateway:** Handles user registration, email verification, password reset flows, and session refresh on the frontend client.
- **FastAPI Backend JWT Verification:** The backend acts as a stateless, cryptographically authoritative verifier. Every incoming API request bearing an `Authorization: Bearer <token>` header is parsed and verified using `app.core.security.decode_token`.
- **Claim Extraction & Role Synchronization:**
  - Standard claims (`sub`, `email`, `aud`, `exp`) are extracted from the JWT payload.
  - Custom claims (`app_metadata.roles`) are verified against the application's RBAC model (`seeker`, `owner`, `tenant`, `pg_operator`, `admin`).
  - Staged fallback: If `SUPABASE_JWT_SECRET` is configured, signature validation uses HMAC-SHA256 (`HS256`); in standalone test environments, fallback to `SECRET_KEY` ensures deterministic automated test passes.

---

## 2. Token Lifecycles & Security Constraints

| Token Type | Issuer | Validity Duration | Refresh Protocol | Invalidation Strategy |
|---|---|---|---|---|
| **Access Token** | Supabase Auth / Backend | 15 Minutes | Silent background refresh via Supabase Client | Replaced on expiry; revoked on password change. |
| **Refresh Token** | Supabase Auth | 7 Days | Stored in HTTP-only, Secure, SameSite=Lax cookie | Rotated on use; revoked on explicit logout. |
| **Password Reset Token** | Backend Auth Service | 15 Minutes | One-time URL token parameter | Single-use non-reusable token invalidated upon password reset. |

---

## 3. Session Isolation & CSRF Safeguards

1. **Client Storage:**
   - Access tokens are stored in memory in client runtime state (`auth-context.tsx`).
   - Session tokens persist across browser reloads via Supabase client local session management.
2. **CORS & Origin Hardening:**
   - Backend `CORSMiddleware` strictly whitelists explicit frontend origins:
     - Local: `http://localhost:3000`
     - Staging: `https://staging.flatmate.internal`, `https://*.vercel.app`
   - Wildcards (`"*"`) and insecure origins are strictly blocked.
3. **Role-Based Access Control (RBAC):**
   - Route guards in Next.js (`apps/web/lib/auth-guard.tsx`) intercept unauthorized transitions on the client before sensitive dashboards render.
   - FastAPI dependencies (`get_current_user`, `require_role`) enforce strict server-side authorization boundaries, raising `HTTP 403 Forbidden` if a seeker attempts to access owner or admin endpoints.
