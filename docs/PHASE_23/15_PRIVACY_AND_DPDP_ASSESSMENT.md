# PHASE 23.15 — Privacy and Digital Personal Data Protection (DPDP) Act Assessment

**Document Version:** 1.0  
**Phase:** 23.15 — Privacy Engineering & DPDP Technical Assessment  
**Date:** November 14, 2026  
**Auditor Roles:** Data Protection Officer (DPO) Technical Advisor, Application Security Engineer  
**Classification:** Technical Privacy Controls & DPDP Compliance Architecture  
**Jurisdiction:** India (Digital Personal Data Protection Act, 2023)  

---

> [!IMPORTANT]
> **Legal Disclaimer:** This document reviews the implemented *technical architecture and software controls*. It does not constitute formal legal counsel. A qualified Indian data privacy attorney must review terms, privacy policies, and consent notices prior to commercial launch.

---

## 1. Executive Summary

This assessment evaluates the technical privacy architecture of the Flatmate platform against the requirements of India's **Digital Personal Data Protection Act, 2023 (DPDP Act)** and relevant personal data fiduciary obligations.

The platform processes sensitive lifestyle preferences, contact details, identity proofs, and geospatial coordinates. Technical privacy-by-design controls have been implemented across every storage, presentation, and communication layer.

---

## 2. Technical Privacy Controls Matrix (DPDP Alignment)

| DPDP Principle | Statutory Expectation | Implemented Technical Control | Verification Status |
| :--- | :--- | :--- | :---: |
| **Notice & Consent** | Unbundled, granular, revocable consent | Dedicated onboarding agreement with clear purpose specification | **IMPLEMENTED** |
| **Purpose Limitation** | Data used solely for flatmate matching & rental | Verification documents are isolated to KYC approval workflows | **IMPLEMENTED** |
| **Data Minimization** | Collect only necessary personal data | Exact street addresses and phone numbers are hidden from public view | **IMPLEMENTED** |
| **Storage Limitation** | Retain data only as long as necessary | Soft-deletion and account erasure workflows | **IMPLEMENTED** |
| **Data Security Safeguards**| Reasonable security to prevent breach | Bcrypt hashing, ES256 JWKS, TLS encryption, DB RLS | **IMPLEMENTED** |
| **Right to Erasure** | Delete personal data on user request | Account deactivation/deletion wipes profile and cascades | **IMPLEMENTED** |
| **Right to Grievance Redressal**| Transparent user reporting mechanism | In-app report submission (`POST /api/v1/moderation/reports`) | **IMPLEMENTED** |

---

## 3. High-Risk Privacy Implementations

### 3.1 Aadhaar Avoidance Strategy
- Under the Aadhaar (Targeted Delivery of Financial and Other Subsidies, Benefits and Services) Act, 2016 and UIDAI regulations, storing unmasked 12-digit Aadhaar numbers or raw Aadhaar cards creates severe compliance liability.
- **Implementation:** The verification module explicitly instructs users to upload **Passport, Driving License, or Voter ID**. If an identity document is submitted, client-side notices instruct users not to upload raw Aadhaar cards.

### 3.2 Phone Number Privacy & Masking
- Contact numbers are classified as high-risk personally identifiable information (PII).
- **Rule:** A seeker's phone number is **never** displayed to strangers on public cards or search results.
- **Masking:** By default, phone numbers are masked (`+91 98***** 1234`). Only after a mutual match or approved appointment is unmasked contact details shared if the user enabled `show_phone_publicly` or `matched_only` in `user_privacy_settings`.

### 3.3 Geospatial Coordinate Fuzzing
- To prevent stalking and protect residential tenant safety, exact property latitude and longitude coordinates are masked for unauthenticated public searchers.
- **Implementation:** `fuzz_coordinates(lat, lon)` introduces a deterministic pseudo-random offset of $\pm 0.003^\circ$ (~300 meters) in public API responses. Exact coordinates are disclosed only after a verified appointment is confirmed with the property owner.

### 3.4 Verification Document Confidentiality
- Government-issued verification documents are stored in the private bucket `verification-docs`.
- The storage gateway denies direct HTTP downloads and generates short-lived signed URLs (1-hour TTL) accessible solely by the submitting user and authorized platform administrators.

---

## 4. User Rights Workflows (Data Subject Access & Erasure)

- **Account Deactivation:** Sets `user.is_active = false`. Immediately invalidates active sessions and rejects subsequent API token exchanges with `403 Forbidden`.
- **Account Deletion:** Cascades deletion across `profiles`, `lifestyle_profiles`, `user_dealbreakers`, and `user_privacy_settings`, while soft-deleting messages (`is_deleted = true`, content replaced with *"This message was deleted"*).

---

## 5. Next Steps for Launch

1. Finalize the Privacy Policy document detailing Data Fiduciary contact information and Grievance Officer designation under DPDP rules.
2. Conduct formal legal review with licensed Indian privacy counsel.
