# PHASE 23.5 — Authentication and Authorization Audit & Verification

**Document Version:** 1.0  
**Phase:** 23.5 — Supabase Auth Lifecycle & FastAPI Authorization Boundary  
**Date:** November 14, 2026  
**Auditor Roles:** Application Security Engineer, Identity & Access Management (IAM) Specialist  
**Classification:** Cryptographic Token & Authorization Security Audit  
**Identity Provider:** Supabase Auth (`https://qjwitdovbsfviaepjcul.supabase.co`)  
**Authorization Authority:** FastAPI Server-Side RBAC (`apps/api/app/core/dependencies.py`)  

---

## 1. Executive Summary

This report documents the end-to-end audit of user authentication and authorization across the Next.js 14 frontend and FastAPI backend.

In strict compliance with **Non-Negotiable Rule 0**:
- **Live Supabase Auth Verified:** Verified admin user provisioning, password grant authentication, JWT issuance, and user deletion directly against the real Supabase Auth endpoint (`/auth/v1/`).
- **Server-Side Authorization Boundary:** Frontend route guards provide UX navigation hints only. Every data operation is strictly enforced at the FastAPI backend and PostgreSQL database levels.
- **Fail-Closed Security:** Insecure fallback tokens are prohibited in staging and production environments.

---

## 2. Frontend Authentication Lifecycle (`apps/web`)

| Lifecycle Stage | Implementation Path | Verification Status | Details |
| :--- | :--- | :--- | :--- |
| **Registration** | `/register`, `apps/web/app/(auth)/register/page.tsx` | **VERIFIED** | Form validation, role selection (`seeker`, `owner`, `tenant`, `pg_operator`), disallows admin self-assignment. |
| **Email Verification** | Supabase Auth `/auth/v1/verify` | **VERIFIED** | Email confirmation links directed through Next.js callback route. |
| **Login** | `/login`, `apps/web/app/(auth)/login/page.tsx` | **VERIFIED** | Validates email/password, stores secure cookies via `@supabase/ssr`, redirects to role dashboard. |
| **Logout** | Global header / user menu | **VERIFIED** | Clears session cookie via `supabase.auth.signOut()`, redirects to `/login`. |
| **Session Restoration** | `apps/web/middleware.ts` & `utils/supabase/middleware.ts` | **VERIFIED** | Automatically intercepts requests, calls `getUser()`, preserves session across navigation. |
| **Token Refresh** | `@supabase/ssr` cookie handler | **VERIFIED** | Transparently exchanges refresh tokens before expiration without user interruption. |
| **Password Recovery** | `/forgot-password`, `apps/web/app/(auth)/forgot-password/page.tsx` | **VERIFIED** | Triggers password reset email via Supabase Auth API. |
| **Password Reset** | `/reset-password`, `apps/web/app/(auth)/reset-password/page.tsx` | **VERIFIED** | Consumes password recovery token and updates bcrypt password hash. |
| **Expired Sessions** | `apps/web/lib/api-client.ts` | **VERIFIED** | Intercepts HTTP 401 Problem Details, flushes stored state, and routes to `/login?expired=true`. |
| **Protected Pages** | Next.js App Router route guards | **VERIFIED** | Protects `/dashboard`, `/profile`, `/owner/*`, `/admin/*`, `/messages`, `/appointments`. |
| **Role-Aware Navigation** | Header & sidebar navigation | **VERIFIED** | Dynamic navigation renders owner links only to `owner`/`pg_operator` and admin links only to `admin`. |

---

## 3. Backend Authorization & JWT Verification (`apps/api`)

### 3.1 Cryptographic Token Verification
- **Primary Mechanism:** `decode_token(token)` in `apps/api/app/core/security.py` verifies signatures using `SUPABASE_JWT_SECRET` (HS256) and asymmetric key resolution via `SUPABASE_JWKS_URL` (`.well-known/jwks.json`).
- **Claim Validations:**
  - `sub`: Must be a valid UUID corresponding to an active `User` record in the database.
  - `exp`: Strictly evaluated against current UTC time.
  - `type`: Must explicitly equal `"access"`; refresh tokens rejected on API endpoints.
  - In staging and production, fallback to development secrets is strictly prohibited.

### 3.2 Role-Based Access Control (RBAC)
FastAPI dependency `require_roles(allowed_roles: List[str])` validates user roles against database records rather than unverified client claims:

```python
def require_roles(allowed_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_roles = [current_user.role]
        if "roles" in current_user.__dict__ and current_user.__dict__["roles"]:
            user_roles.extend([r.role for r in current_user.__dict__["roles"]])
        if "super_admin" in user_roles or "admin" in user_roles:
            return current_user
        if not any(role in allowed_roles for role in user_roles):
            raise ForbiddenException("Insufficient permissions for this operation")
        return current_user
    return role_checker
```

### 3.3 Resource Ownership & Tenant Isolation
FastAPI dependency `verify_resource_ownership(resource_owner_id, current_user, admin_override=True)` guarantees:
- A user can only access, edit, or delete their own profile, applications, listings, or messages.
- Cross-tenant access attempts immediately trigger an RFC 7807 `403 Forbidden` exception.

---

## 4. Multi-Role Empirical Validation Matrix

All 7 required user roles and trust boundaries were validated in `apps/api/tests/test_auth_rbac.py` and `scripts/test_rls_policies.py`:

| Test Boundary | Actor Role | Target Resource | Expected Outcome | Empirical Result |
| :--- | :--- | :--- | :--- | :--- |
| **Seeker vs Owner** | `seeker` | `POST /api/v1/properties/` (Create Listing) | HTTP 403 Forbidden | **PASS (Denied)** |
| **Owner vs Owner** | `owner` A | Property belonging to `owner` B | HTTP 403 Forbidden | **PASS (Denied)** |
| **Group Boundary** | `seeker` C | Group syndicate of members A & B | HTTP 403 Forbidden | **PASS (Denied)** |
| **Removed Member**| Removed user | Group chat & wishlist after removal | HTTP 403 Forbidden | **PASS (Access Revoked)** |
| **Blocked User** | Blocked user | Messaging blocker user | HTTP 403 Forbidden | **PASS (Blocked)** |
| **Admin Audit** | `admin` | Moderation & user deactivation | Audit logged in `outbox_events` | **PASS (Audit Trail Preserved)** |
| **Client Spoofing** | Attacker | Forged `role: "admin"` in body | Server ignores body, queries DB | **PASS (Enforced from DB)** |

---

## 5. Security Conclusion & Status

- **Status:** **`VERIFIED AGAINST REAL HOSTED SERVICE`** (Supabase Auth API live lifecycle) + **`VERIFIED LOCALLY`** (FastAPI RBAC & Database RLS).
- **Audit Result:** Zero horizontal privilege escalations (BOLA/IDOR), zero vertical privilege escalations, and strict fail-closed authorization.
