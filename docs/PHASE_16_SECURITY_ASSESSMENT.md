# Phase 16 — Comprehensive Security Assessment
## Flatmate Compatibility & Rental Marketplace

**Assessor:** Senior Security Engineer & Independent Code Auditor  
**Date:** 2026-11-13  
**Standard:** OWASP Top 10 (API Security), GDPR / India DPDP Act Privacy Alignment  
**Status:** **REMEDIATION IN PROGRESS**

---

## 1. Executive Summary & Threat Model

The Flatmate Compatibility & Rental Marketplace processes sensitive personal data, including government identification documents, phone numbers, precise home addresses, sleep/lifestyle routines, and financial tenancy transactions. 

The threat model identifies five critical attack vectors:
1. **Broken Object-Level Authorization (BOLA/IDOR)** allowing malicious users to read private tenancy applications, view appointments, and manipulate group memberships.
2. **Geospatial De-anonymization & Stalking** through coordinate precision leaks, alternate endpoint queries, and trilateration attacks.
3. **Private Lifestyle Leakage** through explainability strings exposing a counterpart's intimate lifestyle responses.
4. **Identity & Authentication Bypass** via insecure JWT secret fallback.
5. **Concurrency Exploits** leading to overbooking and inconsistent bed reservations.

---

## 2. Vulnerability Classification Matrix

| Finding ID | Classification | Severity | Affected Component | Status |
| :--- | :--- | :---: | :--- | :---: |
| **SEC-01** | Broken Object-Level Authorization (IDOR) | **CRITICAL** | `GET /api/v1/applications/{application_id}` | Needs Fix |
| **SEC-02** | Unauthenticated Information Disclosure | **CRITICAL** | `GET /api/v1/appointments/{appointment_id}` | Needs Fix |
| **SEC-03** | Broken Group Authorization (BOLA) | **HIGH** | `POST /api/v1/groups/{group_id}/members` | Needs Fix |
| **SEC-04** | Unauthorized Wishlist Interaction (BOLA) | **HIGH** | `POST /api/v1/groups/{group_id}/wishlist/{property_id}/vote` | Needs Fix |
| **SEC-05** | Sensitive Location Disclosure & Trilateration | **HIGH** | `POST /api/v1/search/properties` & `GET /properties/{id}` | Needs Fix |
| **SEC-06** | JWT Fallback Secret Bypass | **HIGH** | `app/core/security.py` (`decode_token`) | Needs Fix |
| **SEC-07** | Concurrency Race Condition on Bed Booking | **HIGH** | `PropertyService.assign_bed_occupant` | Needs Fix |
| **SEC-08** | Plaintext PII Leak in Matching Explanations | **MEDIUM** | `app/modules/matching/engine.py` | Needs Fix |
| **SEC-09** | Missing Server-Side File Upload & MIME Validation | **MEDIUM** | `app/modules/verification/service.py` | Needs Fix |
| **SEC-10** | Missing In-App Token Blacklist / Revocation | **MEDIUM** | `POST /api/v1/auth/logout` | Needs Fix |
| **SEC-11** | In-Memory Rate Limiting Scope | **LOW** | `app/core/rate_limit.py` | Documented |
| **SEC-12** | Ineffective Row-Level Security via Single App Connection | **HIGH** | `database/policies/rls_policies.sql` | Documented / Hardened at App Layer |

---

## 3. Deep Vulnerability Analyses

### SEC-01: IDOR on Tenancy Applications (CRITICAL)
- **Vulnerability:** An authenticated user can inspect any other user's rental application by supplying its UUID to `GET /api/v1/applications/{application_id}`.
- **Impact:** Complete exposure of applicant income proposals, move-in dates, personal self-introductions, and attached verification document URLs.
- **Remediation:** Verify caller ownership (`current_user.id == app.applicant_id` OR `current_user.id == property.owner_id` OR admin). Reject with HTTP 403 Forbidden.

---

### SEC-02: Unauthenticated Viewing Appointment Leak (CRITICAL)
- **Vulnerability:** `GET /api/v1/appointments/{appointment_id}` does not declare authentication dependencies.
- **Impact:** Anyone on the internet can read physical address visit schedules, virtual meeting links, host user IDs, and visitor user IDs.
- **Remediation:** Enforce `Depends(get_current_user)` and ensure caller is host, applicant, or admin.

---

### SEC-03 & SEC-04: Group BOLA on Membership & Wishlist (HIGH)
- **Vulnerability:** `add_group_member` and `vote_wishlist` do not check whether the requester is an authorized leader or active member of the target group.
- **Impact:** Malicious actors can inject arbitrary users into private flatmate syndicates and poison property voting tallies.
- **Remediation:** Enforce strict group membership validation before permitting member additions or wishlist votes.

---

### SEC-05: Geospatial Coordinate Privacy & Trilateration (HIGH)
- **Vulnerability:**
  1. Any logged-in user querying `POST /api/v1/search/properties` receives exact GPS coordinates because `is_authenticated_viewer` was treated as an unmasking flag.
  2. `GET /api/v1/properties/{id}` returns `address_exact` to public callers.
  3. Calculating `distance_km` with 2 decimal places against exact coordinates allows mathematical trilateration from 3 query points.
- **Impact:** Real-world tracking of resident homes without tenant/landlord consent.
- **Remediation:**
  - Keep coordinates fuzzed (~1.1 km) for all search queries regardless of authentication status.
  - Only reveal `address_exact` to verified owners, tenants, or applicants with confirmed bookings.
  - Compute `distance_km` using fuzzed coordinates or truncate distance precision to 1 decimal place.

---

### SEC-06: JWT Secret Fallback Authentication Bypass (HIGH)
- **Vulnerability:** When `SUPABASE_JWT_SECRET` verification fails, `decode_token` falls back to `SECRET_KEY`. If `SECRET_KEY` remains the default development string, tokens signed with the well-known key are accepted as legitimate admin sessions.
- **Impact:** Complete administrative takeover in staging/production environments.
- **Remediation:** Disable default secret fallback when `ENVIRONMENT != "development"`. Enforce minimum 32-character high-entropy secret validation at application startup.

---

### SEC-07: Concurrency Race Condition on Bed Occupancy (HIGH)
- **Vulnerability:** `assign_bed_occupant` executes a standard read before updating `is_occupied` without `SELECT ... FOR UPDATE` row locks.
- **Impact:** Simultaneous requests can assign the same bed to multiple tenants, triggering unhandled DB constraint errors or double-booking.
- **Remediation:** Add `.with_for_update()` to bed selection queries in transactional sessions.

---

### SEC-08: Plaintext Lifestyle Response Leak in Compatibility Engine (MEDIUM)
- **Vulnerability:** Explanations formatted as `f"Cleanliness expectations ({c1}/5 vs {c2}/5)"` or `f"Dietary compatibility ({d1} & {d2})"` expose the counterpart's confidential answers.
- **Impact:** Breach of user privacy preferences.
- **Remediation:** Format explanations using objective comparative statements (e.g. "Cleanliness expectations are well-aligned" or "Differences in dietary preferences noted") without outputting raw survey values.

---

## 4. Remediation Plan

All Critical and High severity findings (SEC-01 through SEC-07) must be resolved immediately, followed by regression test verification.
