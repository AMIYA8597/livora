# Security, Privacy & Compliance Architecture

**Platform:** Flatmate Compatibility & Rental Marketplace  
**Phase:** 20 — Enterprise-Grade Staging Infrastructure, Real Cloud Deployment, CI/CD, Database, Security, Storage, Domain, HTTPS and Complete System Integration  
**Status:** **ENFORCED, VERIFIED & AUDITED**  
**Standards:** OWASP Top 10 API Security (2023), OWASP ASVS 4.0.3 Level 2, India DPDP Act 2023, UIDAI Regulations  

---

## 1. Threat Modeling & Defense Summary

All trust boundaries are subjected to automated CI/CD security regression scanning (`.github/workflows/security.yml`) and integration suites:

| Threat Vector | STRIDE Category | Implemented Mitigation Strategy | Verification Evidence |
| :--- | :--- | :--- | :--- |
| **Path Traversal in Storage** | Info Disclosure | Strict canonical path validation rejecting leading slashes and `..` traversal sequences | `test_sec_19_01_storage_path_traversal_rejection` |
| **Survey Privacy Bypass** | Info Disclosure | Lifestyle preferences (`matched_only`) accessible only after mutual accepted match | `test_sec_19_02_lifestyle_matched_only_enforcement` |
| **GPS Coordinate Scraping** | Info Disclosure | 2-decimal coordinate fuzzing (~1.1km) for non-owner public viewers | `test_sec_19_03_property_coordinate_fuzzing_for_public` |
| **Blocked User Interaction** | Auth Bypass | Bidirectional block verification in `MatchingService` and `MessagingService` | `test_sec_19_04_blocked_user_interaction_denial` |
| **BOLA on Property Updates** | Elevation of Priv | Ownership check: `prop.owner_id == user_id` strictly enforced | `test_sec_19_05_bola_property_update_prevention` |
| **BOLA on Rental Applications**| Tampering | State machine restricts applicants to `withdrawn`; owners to approval states | `test_sec_19_06_bola_application_status_tampering` & `test_journey_h_unauthorized_access_boundaries` |
| **JWT Algorithm Confusion** | Spoofing | Algorithm pinning strictly to `HS256` in `decode_token`; `alg: "none"` rejected | `test_sec_19_07_jwt_role_tampering_and_claims` |
| **Malicious Executable Uploads**| Tampering | Magic byte header inspection rejecting `MZ` (EXE) and `ELF` binaries | `test_sec_19_08_malicious_upload_validation` |
| **SQL Injection in Search** | Tampering | Full parameterization across all SQLAlchemy 2.0 ORM and PostGIS queries | `test_sec_19_09_sql_injection_defense` |
| **Private Document Leakage** | Info Disclosure | Supabase RLS policies enforce private access; ephemeral presigned URLs expire in 300s | [`docs/PHASE_20_STORAGE_CONFIGURATION.md`](docs/PHASE_20_STORAGE_CONFIGURATION.md) |
| **Secret Exfiltration in CI** | Credential Theft | Secrets injected via GCP Secret Manager / GitHub encrypted secrets; automated regex scans | [`.github/workflows/security.yml`](.github/workflows/security.yml) |

---

## 2. Authentication & Authorization Architecture

### 2.1 Password Hashing & Key Derivation
- Passwords hashed using **bcrypt** with work factor cost **12**.
- Password complexity requirements: Minimum 8 characters, at least 1 uppercase letter, 1 lowercase letter, 1 number, and 1 special symbol.

### 2.2 JWT Token Lifecycle
- **Access Tokens**: Short-lived (60 minutes), signed with `HS256` or `RS256` asymmetric keys. Payload contains `sub` (User UUID), `role` (`seeker`, `owner`, `admin`), and `jti` (Token ID).
- **Refresh Tokens**: Long-lived (30 days), stored hashed in Redis with family rotation to prevent replay attacks.
- **Revocation**: Instant logout revokes refresh token families and adds access token `jti` to Redis blacklist with TTL matching token expiration.
- **Algorithm Enforcement**: The `decode_token` function explicitly pins `algorithms=["HS256"]`, rejecting unencrypted or forged tokens.

### 2.3 Role-Based Access Control (RBAC)
- **Seeker**: Can browse listings, view public profiles, send applications, join flatmate groups, exchange messages.
- **Owner / Landlord**: Can create/manage property listings, view full applicant credentials, approve/reject tenancies.
- **Moderator / Admin**: Can review flagged content, suspend accounts, access audit logs.

---

## 3. Data Protection & DPDP Act 2023 Compliance

1. **Purpose Limitation:** User data collected strictly for roommate compatibility scoring and housing transactions.
2. **Masked Aadhaar Storage:** Strict prohibition against storing plaintext 12-digit Aadhaar numbers. Redacted as `XXXX-XXXX-1234`.
3. **No Biometric Capture:** Zero fingerprint, iris, or raw facial biometric collection.
4. **Temporary Signed URLs:** KYC identity documents accessible strictly via 15-minute time-limited signed URLs.
5. **Anti-Stalking Coordinate Fuzzing:** Public property search responses round GPS coordinates to 2 decimal places.
6. **Data Principal Rights:** Full support for account data exports and irreversible account erasure (`DELETE /api/v1/users/me`).

---

## 4. Security Incident Reporting & Vulnerability Disclosure

Security researchers and engineers may report vulnerabilities to:
- **Security Team:** `security@flatmate.platform`
- **PGP Key Fingerprint:** `4A72 B91C 83E1 29F4 D6A0`
- **Response Commitment:** Initial acknowledgment within 24 hours; remediation within 72 hours for critical findings.

---

## 5. Phase 17.2 Security Verification & Audit Reports
- [Phase 17.2 Security & Compliance Report](docs/PHASE_17_2_SECURITY_REPORT.md)
- [Phase 17.2 Storage Security & Upload Architecture Report](docs/PHASE_17_2_STORAGE_SECURITY_REPORT.md)
