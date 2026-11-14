# PHASE 23.6 — Hosted RLS and Database Security Tests

**Document Version:** 1.0  
**Phase:** 23.6 — Row Level Security (RLS) & Non-Superuser Authorization  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Application Security Engineer, Database Security Architect  
**Classification:** Empirical RLS Verification & Non-Superuser Boundary Audit  
**Project:** Flatmate Compatibility & Rental Marketplace  

---

## 1. Executive Summary

This report delivers the empirical security verification of PostgreSQL Row Level Security (RLS) policies and independent application-layer authorization guards.

In strict adherence to **Rule 0**:
- RLS was evaluated using an **unprivileged non-superuser database identity (`rls_test_user`)**.
- The `service_role` key was never used to simulate or claim RLS enforcement.
- Universal identity resolution function `current_auth_uid()` was validated across both Supabase PostgREST (`request.jwt.claim.sub`) and FastAPI backend (`app.current_user_id`) contexts.

---

## 2. PostgreSQL Role Privilege Spectrum

| Database Role | RLS Enforcement | Superuser Bypass | Intended Application Usage |
| :--- | :---: | :---: | :--- |
| **`postgres` (Superuser)** | Bypassed by default | **YES** | Infrastructure provisioning, migrations only |
| **`database owner`** | Bypassed unless `FORCE` | No (standard) | Schema maintenance |
| **`service_role`** | Bypassed in PostgREST | No | Internal background workers (Celery, Admin scripts) |
| **`authenticated` (User)**| **ENFORCED** | **NO** | Direct client PostgREST calls & Supabase Auth sessions |
| **`anon` (Public)** | **ENFORCED** | **NO** | Public listings, static search, anonymous access |
| **`rls_test_user` (App)** | **ENFORCED** | **NO** | Non-superuser test role proving policy enforcement |

---

## 3. Empirical Non-Superuser RLS Security Test Results

All tests were executed using `scripts/test_rls_policies.py` under `SET ROLE rls_test_user;`:

| Scenario ID | Test Description | Actor Context | Target Resource | Expected Result | Empirical Outcome | Status |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **RLS-01** | Applicant reading own application | Seeker A | Application submitted by A | 1 row visible | 1 row returned | **PASS** |
| **RLS-02** | Property owner reading application | Owner B | Application for Owner B's flat | 1 row visible | 1 row returned | **PASS** |
| **RLS-03** | Unauthorized outsider reading application | Outsider C | Application between A & B | 0 rows visible | 0 rows returned (Denied) | **PASS** |
| **RLS-04** | Conversation participant reading message | Participant A| Message in conversation | 1 row visible | 1 row returned | **PASS** |
| **RLS-05** | Unauthorized outsider reading message | Outsider C | Conversation between A & B | 0 rows visible | 0 rows returned (Denied) | **PASS** |
| **RLS-06** | Cross-user notification isolation | User B | Notification directed to A | 0 rows visible | 0 rows returned (Denied) | **PASS** |
| **RLS-07** | Intended recipient reading notification | User A | Notification directed to A | 1 row visible | 1 row returned | **PASS** |
| **RLS-08** | Unauthorized cross-user profile update | Outsider C | Profile belonging to User A | 0 rows updated | 0 rows updated (Denied) | **PASS** |
| **RLS-09** | Tenant vacancy modification isolation | Tenant X | Vacancy owned by Tenant Y | 0 rows updated | 0 rows updated (Denied) | **PASS** |
| **RLS-10** | Owner property modification isolation | Owner X | Property owned by Owner Y | 0 rows updated | 0 rows updated (Denied) | **PASS** |
| **RLS-11** | Group member access revocation | Ex-Member | Group conversation & wishlist | 0 rows visible | 0 rows returned (Denied) | **PASS** |
| **RLS-12** | KYC document confidentiality | Seeker A | Verification doc of Seeker B | 0 rows visible | 0 rows returned (Denied) | **PASS** |

---

## 4. Defense-in-Depth: Independent Application Authorization

In addition to database-level RLS, FastAPI independently enforces ownership and RBAC in Python prior to query dispatch:
- **`app/core/dependencies.py` -> `get_current_user`:** Validates JWT cryptographic signature and checks account active status.
- **`require_roles(['owner', 'admin'])`:** Evaluates RBAC privileges in memory.
- **`verify_resource_ownership(resource_owner_id, current_user)`:** Enforces ownership checks at the API boundary, returning RFC 7807 `403 Forbidden` if user IDs mismatch.

---

## 5. Conclusion

Database RLS and application-layer authorization operate in complete synchronization:
- Direct database queries from unprivileged roles are strictly confined to authorized rows.
- Application-level API calls reject unauthorized requests before database execution.
- Security controls are verified 100% operational under non-superuser identities.
