# Phase 19 — Comprehensive Security Threat Model & STRIDE Analysis

**Project:** Flatmate Compatibility & Rental Marketplace  
**Document ID:** `SEC-19-TM-01`  
**Phase:** 19 — Full-System Quality Assurance, Adversarial Security Testing & Release Candidate Verification  
**Evaluation Standard:** STRIDE, OWASP Top 10 API Security (2023), OWASP ASVS 4.0.3 Level 2  
**Author:** Principal Application Security Engineer  
**Date:** November 2026  
**Status:** VALIDATED & BASELINED  

---

## 1. Executive Summary

This document establishes the formal Security Threat Model for the Flatmate Compatibility & Rental Marketplace platform. The platform handles highly sensitive personal data, including lifestyle routines, personality vectors, housing applications, financial deposits, government-issued identity documents (Aadhaar/PAN/Passport), and private tenant communications.

Through systematic STRIDE analysis across all 6 architectural trust boundaries, this threat model identifies potential attack vectors, evaluates residual risks, and verifies the defense-in-depth controls enforced by FastAPI, PostgreSQL 18, and Next.js 14.

---

## 2. Trust Boundaries & Architecture Diagram

```
+-----------------------------------------------------------------------------------+
| TRUST BOUNDARY 0: UNTRUSTED INTERNET                                             |
| External Clients: Next.js 14 Web App, Mobile Browsers, Adversarial HTTP Clients     |
+-----------------------------------------------------------------------------------+
                                    | (TLS 1.3 / HTTPS / WSS)
                                    v
+-----------------------------------------------------------------------------------+
| TRUST BOUNDARY 1: EDGE & REVERSE PROXY                                            |
| Rate Limiting (SlowAPI), CORS Middleware, Security Headers (CSP, HSTS)             |
+-----------------------------------------------------------------------------------+
                                    | (Reverse Proxy / Forwarded Headers)
                                    v
+-----------------------------------------------------------------------------------+
| TRUST BOUNDARY 2: APPLICATION RUNTIME (FastAPI Backend)                          |
| Bearer JWT Validation, RBAC Enforcement, Pydantic v2 Contract Validation,         |
| Service Layer Business Logic & BOLA Guards                                       |
+-----------------------------------------------------------------------------------+
          |                                  |                        |
          | (SQLAlchemy 2.0 Async / asyncpg) | (Celery / Redis / AMQP)| (S3 / Local Storage)
          v                                  v                        v
+-----------------------------------+  +-----------------------+  +-------------------+
| TRUST BOUNDARY 3: PERSISTENCE     |  | TRUST BOUNDARY 4:     |  | TRUST BOUNDARY 5: |
| PostgreSQL 18 + PostGIS + pgvector|  | ASYNC WORKERS         |  | OBJECT STORAGE    |
| Row-Level Security, Encrypted     |  | Celery Task Worker,   |  | Signed URLs, MIME |
| Columns, ACID Transactions        |  | Redis Event Broker    |  | Magic Validation  |
+-----------------------------------+  +-----------------------+  +-------------------+
```

### Trust Boundary Definitions

1. **TB-0 -> TB-1 (Client to Edge):** Untrusted web clients crossing network boundaries. Susceptible to volumetric DDoS, credential stuffing, and MITM.
2. **TB-1 -> TB-2 (Edge to Application):** Request headers, cookies, and bearer tokens ingested by FastAPI. Susceptible to spoofed forwarded headers, algorithm confusion (`alg: none`), and payload tampering.
3. **TB-2 -> TB-3 (Application to Database):** Parameterized SQL queries via SQLAlchemy 2.0 asyncpg. Protected against SQL injection; requires strict connection pooling and concurrency isolation.
4. **TB-2 -> TB-4 (Application to Asynchronous Workers):** Task queuing via Redis/Celery. Susceptible to payload tampering, deserialization attacks, and task queue starvation.
5. **TB-2 -> TB-5 (Application to Object Storage):** File storage abstraction. Susceptible to path traversal, MIME spoofing, and malicious executable uploads.

---

## 3. Threat Actor Profiles

| Actor Profile | Description | Access Level | Motivations & Goals |
| :--- | :--- | :--- | :--- |
| **TA-01: External Unauthenticated Attacker** | Internet user, botnet operator, or scraper | None (Public endpoints) | Data scraping (phone numbers, locations), credential stuffing, DoS via complex PostGIS/matching queries. |
| **TA-02: Malicious Registered Seeker** | Authenticated tenant looking for housing | `seeker` role token | Scraping roommate private surveys, spoofing lifestyle vectors for artificial 99% match, bypassing application workflows. |
| **TA-03: Rogue Property Owner / PG Operator** | Registered landlord or PG manager | `owner` role token | Modifying other owners' properties (BOLA), forging rental approval states, scraping applicant identity documents. |
| **TA-04: Malicious Roommate / Group Member** | Co-tenant or shared search group member | `seeker` / `group_member` | Unauthorized group deletion, removing co-members without consensus, reading unshared financial data. |
| **TA-05: Compromised Internal Service** | Subverted background task or compromised worker | Celery worker process | Unauthorized mass notification emission, unlogged state tampering, database exfiltration. |

---

## 4. Comprehensive STRIDE Threat Catalog

### 4.1 Spoofing (S)

| Threat ID | Target Asset | Attack Vector | Implemented Countermeasure | Residual Risk |
| :--- | :--- | :--- | :--- | :--- |
| **STRIDE-S-01** | JWT Authentication | Attacker uses `alg: "none"` or signs token with arbitrary secret | `app.core.security.decode_token` explicitly enforces `algorithms=["HS256"]` and rejects unsigned or wrongly-keyed tokens. | LOW |
| **STRIDE-S-02** | User Identity | Attacker assumes another user's ID via path parameter | `get_current_active_user` extracts `sub` strictly from cryptographically validated JWT; route dependencies enforce `current_user.id == target_id` or admin privileges. | LOW |
| **STRIDE-S-03** | Supabase Session | Attacker presents expired refresh token or forged session | Dual token verification (`SUPABASE_JWT_SECRET` with local HS256 fallback strictly in dev mode; expired tokens immediately return `{}`). | LOW |

### 4.2 Tampering (T)

| Threat ID | Target Asset | Attack Vector | Implemented Countermeasure | Residual Risk |
| :--- | :--- | :--- | :--- | :--- |
| **STRIDE-T-01** | Rental Application Status | Applicant attempts to set status directly to `approved` | `ApplicationService.update_status` enforces strict state machine: seekers may only set `withdrawn`; owners may only progress valid transitions (`submitted -> reviewing -> shortlisted -> approved`). | LOW |
| **STRIDE-T-02** | Room / Bed Inventory | Concurrent seekers simultaneously book the same bed | `with_for_update()` row-level pessimistic locking on `Bed` model inside transactional boundaries prevents double-booking. | LOW |
| **STRIDE-T-03** | Compatibility Scores | Attacker submits crafted lifestyle survey with out-of-range scores | Pydantic v2 schemas (`LifestylePreferencesCreate`) enforce strict enum and range validation (`1 <= clean_level <= 5`, `Ge(0)`, `Le(100)`). | LOW |
| **STRIDE-T-04** | Chat Messages | Sender alters message text after recipient read | Real-time messaging service enforces immutable message logs; status flags (`delivered`, `read`) are isolated from payload bodies. | LOW |

### 4.3 Repudiation (R)

| Threat ID | Target Asset | Attack Vector | Implemented Countermeasure | Residual Risk |
| :--- | :--- | :--- | :--- | :--- |
| **STRIDE-R-01** | Rental Agreement Acceptance | Landlord or tenant claims they never signed agreement | Digital agreement audit trail records user ID, UTC timestamp, IP address, and document hash in `agreements` and `audit_logs` tables. | LOW |
| **STRIDE-R-02** | Moderation & Reporting Actions | Moderator deletes report without audit trace | Every moderation decision (`dismissed`, `actioned`, `escalated`) creates an immutable record in `moderation_reports` with moderator ID. | LOW |
| **STRIDE-R-03** | Sensitive Profile Deletions | User claims account was deleted without consent | Account deletion protocol requires active re-authentication, revokes active refresh tokens, and retains an anonymized audit marker. | LOW |

### 4.4 Information Disclosure (I)

| Threat ID | Target Asset | Attack Vector | Implemented Countermeasure | Residual Risk |
| :--- | :--- | :--- | :--- | :--- |
| **STRIDE-I-01** | Exact Property GPS Coordinates | Attacker scrapes exact building locations to stalk occupants | `PropertyService._format_property_response` automatically fuzzes coordinates to 2 decimal places (~1.1 km) for public non-owner viewers. (Verified SEC-19-03). | LOW |
| **STRIDE-I-02** | Lifestyle & Private Habits | Stalker views detailed habits of unmatched users | `GET /api/v1/lifestyle/{user_id}` enforces privacy preferences (`matched_only`, `mutual_accepted`); returns 403 Forbidden to non-matched seekers. (Verified SEC-19-02). | LOW |
| **STRIDE-I-03** | User Contact Details | Unverified users harvest phone numbers & emails | Phone numbers are masked by default (`formatIndianPhoneNumber`); exposed only upon accepted rental agreement or mutual visit confirmation. | LOW |
| **STRIDE-I-04** | KYC & Identity Documents | Attacker accesses Aadhaar / PAN PDFs via predictable storage URL | Signed URLs with strict 15-minute expiration generated through `StorageService`; directory traversal blocked via canonical path resolution. (Verified SEC-19-01). | LOW |
| **STRIDE-I-05** | Production Stack Traces | Error conditions reveal database schemas and system paths | Custom exception handlers in `app.core.exceptions` intercept all uncaught errors, logging tracebacks internally and returning sanitized JSON error details. | LOW |

### 4.5 Denial of Service (D)

| Threat ID | Target Asset | Attack Vector | Implemented Countermeasure | Residual Risk |
| :--- | :--- | :--- | :--- | :--- |
| **STRIDE-D-01** | PostGIS Geospatial Search | Complex polygon search with 1,000 km radius exhausts CPU | Spatial queries bound radius to maximum allowed threshold (50 km); spatial index (`idx_properties_location_gist`) on `location` geometry. | MEDIUM |
| **STRIDE-D-02** | pgvector Nearest Neighbor | Unbounded `cosine_distance` queries across full user base | HNSW/IVFFlat index on `lifestyle_embeddings`; candidate set pre-filtered by hard constraints (budget, city) before vector ranking. | LOW |
| **STRIDE-D-03** | File Upload Flooding | Attacker uploads multi-gigabyte files to deplete disk | Strict file size limit (10MB for images, 15MB for documents) enforced in `StorageService.validate_file` before buffering. | LOW |
| **STRIDE-D-04** | WebSocket Connection Starvation | Script opens thousands of unauthenticated chat sockets | WebSocket handshake requires valid JWT authentication parameter; idle timeout and per-user socket connection limits enforced. | MEDIUM |

### 4.6 Elevation of Privilege (E)

| Threat ID | Target Asset | Attack Vector | Implemented Countermeasure | Residual Risk |
| :--- | :--- | :--- | :--- | :--- |
| **STRIDE-E-01** | Administrative Endpoints | Regular user accesses `/api/v1/admin/*` | `require_roles("admin")` dependency verifies claims; rejects non-admin users with 403 Forbidden. | LOW |
| **STRIDE-E-02** | BOLA on Property Management | Owner A updates or deletes Owner B's listing | `PropertyService.update` and `delete` query checks `prop.owner_id == user_id` unless caller has `admin` role. (Verified SEC-19-05). | LOW |
| **STRIDE-E-03** | BOLA on Profile Settings | User modifies another user's privacy settings | `ProfileService` and `UserService` enforce strict ownership validation on `user_id`. | LOW |
| **STRIDE-E-04** | Blocked User Circumvention | Blocked user sends messages or books property of blocker | `MatchingService` and `MessagingService` check bidirectional block status in `user_blocks` table and deny interaction. (Verified SEC-19-04). | LOW |

---

## 5. Data Classification Policy

| Classification Level | Examples | Access Controls | Storage Controls | Masking / Redaction Rules |
| :--- | :--- | :--- | :--- | :--- |
| **Level 1: Public** | Property titles, city, neighborhood, amenities, rent range, fuzzed GPS coordinates | Unauthenticated read | Plaintext PostgreSQL | Exact address hidden; coordinates fuzzed to 2 decimal places. |
| **Level 2: Authenticated** | User first name, profile avatar, public compatibility badge | Registered users | Plaintext PostgreSQL | Last name initial only; exact age masked into age brackets. |
| **Level 3: Matched / Connected** | Compatibility breakdown scores, lifestyle survey answers, chat messages | Mutual match or mutual interest confirmation | Plaintext PostgreSQL with RBAC & BOLA guards | Accessible only when match status is `accepted` or `matched`. |
| **Level 4: Confidential** | Rental agreements, applicant bank statements, phone numbers, exact residential address | Property owner & respective tenant/applicant only | Encrypted at rest (AES-256), signed URLs | Phone masked as `+91 98**** *123`; address released only on confirmed visit. |
| **Level 5: Strictly Confidential** | Aadhaar numbers, PAN cards, government photo IDs, JWT signing secrets | User owner & certified verification agent | Signed URLs, zero long-term unencrypted caching | Aadhaar numbers masked (first 8 digits hidden); storage in isolated private bucket. |

---

## 6. Threat Mitigation Matrix & Verification Summary

| Threat Code | Category | Severity | Implemented Mitigation | Verification Mechanism | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SEC-19-01** | Info Disclosure | HIGH | Path traversal check in `StorageService` & `LocalStorageProvider` | `test_sec_19_01_storage_path_traversal_rejection` | **VERIFIED** |
| **SEC-19-02** | Info Disclosure | HIGH | Privacy settings enforcement in `GET /lifestyle/{user_id}` | `test_sec_19_02_lifestyle_matched_only_enforcement` | **VERIFIED** |
| **SEC-19-03** | Info Disclosure | MEDIUM | 2-decimal GPS fuzzing for public non-owners | `test_sec_19_03_property_coordinate_fuzzing_for_public` | **VERIFIED** |
| **SEC-19-04** | Auth Bypass | HIGH | Bidirectional block verification in `MatchingService` | `test_sec_19_04_blocked_user_interaction_denial` | **VERIFIED** |
| **SEC-19-05** | BOLA / IDOR | HIGH | Ownership check in `PropertyService.update` | `test_sec_19_05_bola_property_update_prevention` | **VERIFIED** |
| **SEC-19-06** | BOLA / IDOR | HIGH | State transition & role guards in `ApplicationService.update_status` | `test_sec_19_06_bola_application_status_tampering` | **VERIFIED** |
| **SEC-19-07** | Spoofing | CRITICAL | Algorithm pinning (`HS256`) and signature validation in `decode_token` | `test_sec_19_07_jwt_role_tampering_and_claims` | **VERIFIED** |
| **SEC-19-08** | Tampering | HIGH | Binary magic header validation in `StorageService.validate_file` | `test_sec_19_08_malicious_upload_validation` | **VERIFIED** |
| **SEC-19-09** | Tampering | HIGH | SQLAlchemy 2.0 ORM parameterization across all queries | `test_sec_19_09_sql_injection_defense` | **VERIFIED** |

---

## 7. Residual Risk Statement & Conclusion

All identified high and critical threats in the application and database tiers have been mitigated and verified via automated regression tests in `apps/api/tests/security/test_security_regressions.py`. Residual risks are limited to infrastructure-level DDoS and WebSocket connection exhaustion, which must be addressed by staging reverse proxy rate-limiting (e.g. Nginx, Cloudflare) prior to full public production deployment.
