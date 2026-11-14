# Phase 21.9 — Application Security Assessment & Threat Audit

**Audit Date:** 2026-11-14  
**Assessor:** Principal Application Security Engineer & DevSecOps Lead  
**Scope:** Frontend (Next.js), Backend (FastAPI), Storage (Local/Supabase), Database (PostgreSQL RLS)  
**Security Regression Status:** **14 / 14 TESTS PASSED (100%)**  
**Static Code Analysis (Bandit):** **0 VULNERABILITIES IDENTIFIED**  

---

## 1. Security Architecture & Controls Overview

| Security Domain | Implemented Control | Enforcement Mechanism | Verification Status |
|-----------------|---------------------|-----------------------|:-------------------:|
| **Transport Layer Security** | TLS 1.3 / HSTS Preload | Edge proxy headers (`Strict-Transport-Security: max-age=63072000`) | **PASS** |
| **Authentication & Tokens** | HS256 JWT with >= 32-char high-entropy secret | PyJWT claims validation (`exp`, `sub`, `role`) with fail-closed 401 | **PASS** |
| **Row Level Security (RLS)** | PostgreSQL native RLS policies on multi-tenant tables | Non-superuser DB role `flatmate_staging_user` | **PASS** |
| **BOLA / IDOR Prevention** | Explicit tenancy & resource ownership checks | Dependency guards + service-layer UUID authorization | **PASS** |
| **Admin Route Protection** | Role-Based Access Control (RBAC) | `RoleChecker(["admin", "super_admin"])` | **PASS** |
| **Storage & Upload Security** | Magic byte sniffing, extension whitelist, 10MB ceiling | MIME type validation + path traversal sanitizer | **PASS** |
| **Rate Limiting & DoS** | Sliding window per IP / User | `SlidingWindowRateLimiter` with HTTP 429 & Retry-After | **PASS** |
| **Data Protection & Privacy** | Exact coordinate fuzzing + Aadhaar/PII log redaction | DPDP Act (India) compliance filters + `RedactingFormatter` | **PASS** |

---

## 2. Security Regression Test Suite Results

```
============================= test session starts =============================
collected 14 items

apps/api/tests/security/test_security_regressions.py::test_sec_19_01_storage_path_traversal_rejection PASSED [  7%]
apps/api/tests/security/test_security_regressions.py::test_sec_19_02_lifestyle_matched_only_enforcement PASSED [ 14%]
apps/api/tests/security/test_security_regressions.py::test_sec_19_03_property_coordinate_fuzzing_for_public PASSED [ 21%]
apps/api/tests/security/test_security_regressions.py::test_sec_19_04_blocked_user_interaction_denial PASSED [ 28%]
apps/api/tests/security/test_security_regressions.py::test_sec_19_05_bola_property_update_prevention PASSED [ 35%]
apps/api/tests/security/test_security_regressions.py::test_sec_19_06_bola_application_status_tampering PASSED [ 42%]
apps/api/tests/security/test_security_regressions.py::test_sec_19_07_jwt_role_tampering_and_claims PASSED [ 50%]
apps/api/tests/security/test_security_regressions.py::test_sec_19_08_malicious_upload_validation PASSED [ 57%]
apps/api/tests/security/test_security_regressions.py::test_sec_19_09_sql_injection_defense PASSED [ 64%]
apps/api/tests/test_security_hardening.py::test_security_headers_present PASSED [ 71%]
apps/api/tests/test_security_hardening.py::test_payload_size_enforcement_413 PASSED [ 78%]
apps/api/tests/test_security_hardening.py::test_rate_limiter_sliding_window PASSED [ 85%]
apps/api/tests/test_security_hardening.py::test_rate_limiter_dependency_blocks PASSED [ 92%]
apps/api/tests/test_security_hardening.py::test_sql_injection_defense PASSED [100%]

============================= 14 passed in 1.03s ==============================
```

---

## 3. Vulnerability Audit & Threat Findings

### Finding SEC-21-01: Outdated Next.js Frontend Framework Dependency
- **Severity:** **HIGH** (Pre-Production Blocker)
- **Affected Component:** `apps/web/package.json` (`next@14.2.4`)
- **Vulnerability Identifiers:** GHSA-f82v-jwr5-mffw, GHSA-p293-qw3h-jr36
- **Description:** Next.js versions `<14.2.25` suffer from potential authorization bypass in middleware and cache poisoning vectors.
- **Reproduction Steps:**
  1. Inspect `apps/web/package.json`: `"next": "14.2.4"`.
  2. Execute `pnpm audit --prod`.
- **Remediation Required:**
  - Upgrade `next` to `>=14.2.25` or `^15.0.0` in `apps/web/package.json`.
  - Re-run `pnpm install` and verify test suite passes.

---

### Finding SEC-21-02: Non-Cryptographic MD5 Usage Flagged by SAST
- **Severity:** **LOW / INFORMATIONAL**
- **Affected Component:** `apps/api/app/infrastructure/external_services/semantic_search.py:74`
- **Vulnerability Identifier:** Bandit B324 (CWE-327)
- **Description:** Static analysis flagged `hashlib.md5()` for feature token projection. While not used for password hashing or cryptographic signing, unflagged MD5 usage triggers compliance alarms.
- **Remediation Taken:**
  - Updated code to pass `usedforsecurity=False`:
    ```python
    h = int(hashlib.md5(token.encode("utf-8"), usedforsecurity=False).hexdigest(), 16)
    ```
  - Re-scan with Bandit reported **0 issues across 8,048 lines of code**.

---

### Finding SEC-21-03: Superuser Postgres Connection Bypasses RLS
- **Severity:** **MEDIUM** (Operational Configuration)
- **Affected Component:** Database configuration / connection strings.
- **Description:** In PostgreSQL, connections authenticated as superuser (`postgres`) bypass all RLS policies regardless of table grants.
- **Remediation Taken:**
  - Staging and production configurations mandate the use of the non-superuser application role `flatmate_staging_user` (`flatmate_app` in production).
  - Explicitly verified with `SET ROLE flatmate_staging_user;` in Phase 21.3 that RLS rules prevent cross-tenant data access.

---

## 4. Privacy & Compliance Audit (DPDP Act 2023 - India)

1. **Aadhaar & Government ID Redaction:**
   - Any 12-digit sequence matching Aadhaar format (`\b\d{4}[ -]?\d{4}[ -]?\d{4}\b`) is automatically masked to `XXXX-XXXX-XXXX` by the logging subsystem.
   - Verification documents are stored in a private bucket with no public read access; downloads require an expiring presigned URL (15-minute TTL).

2. **Location Privacy (Anti-Stalking Protections):**
   - The exact street address and raw latitude/longitude of residential listings are hidden from public property discovery endpoints.
   - Only general locality and city are displayed until a seeker's rental application is approved by the property owner.

3. **Consent & Block Isolation:**
   - When a user blocks another party, the blocked party is prevented from viewing user profiles, sending messages, or creating rental applications targeting the user.
