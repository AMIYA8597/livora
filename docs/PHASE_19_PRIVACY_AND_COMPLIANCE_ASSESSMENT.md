# Phase 19 — Privacy, Regulatory Compliance & DPDP Act 2023 Assessment

**Project:** Flatmate Compatibility & Rental Marketplace  
**Document ID:** `COMP-19-PCA-01`  
**Phase:** 19 — Full-System Quality Assurance, Adversarial Security Testing & Release Candidate Verification  
**Evaluation Standard:** India Digital Personal Data Protection Act, 2023 (DPDP Act), IT Act 2000, UIDAI Aadhaar Regulations  
**Author:** Principal Privacy & Security Compliance Officer  
**Date:** November 2026  
**Status:** COMPLIANT FOR STAGING  

---

## 1. Executive Summary

This assessment evaluates the Flatmate platform's compliance with Indian privacy regulations, specifically the **Digital Personal Data Protection Act, 2023 (DPDP Act)**, the **Information Technology Act, 2000**, and the **Unique Identification Authority of India (UIDAI)** regulations regarding government identity proofs.

The platform implements strict purpose limitation, affirmative user consent tracking, data principal rights (access, rectification, erasure), coordinate fuzzing for stalking prevention, and explicit prohibitions against storing raw biometric or unmasked Aadhaar data.

---

## 2. Regulatory Alignment Matrix (DPDP Act 2023)

| DPDP Act Provision | Statutory Requirement | Platform Technical Implementation | Compliance Status |
| :--- | :--- | :--- | :--- |
| **Section 5: Notice** | Clear, transparent notice explaining data collected and specific processing purpose | Dedicated `/privacy` and `/terms` routes presented during onboarding; itemized breakdown before submitting lifestyle survey. | **COMPLIANT** |
| **Section 6: Consent** | Free, specific, informed, unconditional, and unambiguous consent | Timestamped consent records (`consent_given_at`, `terms_accepted_at`) stored in `user_consents`; opt-in checkboxes for matching. | **COMPLIANT** |
| **Section 7: Legitimate Uses** | Processing strictly necessary for fulfillment of service | Data utilized solely for tenant compatibility calculation, property search, and rental agreement execution. | **COMPLIANT** |
| **Section 8: Data Fiduciary Obligations** | Reasonable security safeguards to prevent personal data breach | AES-256 encryption, TLS 1.3, salted bcrypt password hashing, RBAC authorization, and automated SAST/security regression testing. | **COMPLIANT** |
| **Section 11: Right to Access** | Data Principal's right to obtain summary of personal data processed | `GET /api/v1/users/me` and `GET /api/v1/profiles/me` return comprehensive data exports of user profile, habits, and applications. | **COMPLIANT** |
| **Section 12: Right to Correction & Erasure** | Right to correct inaccurate data and delete personal profile | `PUT /api/v1/users/me` enables correction; `DELETE /api/v1/users/me` cascades account deletion and revokes tokens. | **COMPLIANT** |
| **Section 13: Grievance Redressal** | Readily accessible mechanism for redressing data grievances | Grievance Officer contact details displayed in footer and `/privacy` route; ticket escalation system in `/api/v1/moderation/reports`. | **COMPLIANT** |

---

## 3. Handling of Sensitive Personal Data & Government ID (Aadhaar Policy)

In accordance with the Aadhaar (Targeted Delivery of Financial and Other Subsidies, Benefits and Services) Act, 2016 and UIDAI circulars:

1. **Zero Raw Biometric Capture:** The platform strictly prohibits capturing, processing, or storing fingerprints, iris scans, or raw facial biometric templates.
2. **Masked Aadhaar Number Storage:** Where Aadhaar cards are uploaded for tenant KYC verification:
   - Only the last 4 digits are stored in the database (`masked_aadhaar`: `XXXX-XXXX-1234`).
   - The first 8 digits must be masked by the applicant or automated redaction filter.
3. **Storage Isolation & Access Control:**
   - ID documents are stored in a dedicated private storage bucket.
   - Files are accessible solely via short-lived signed URLs (15-minute expiration) generated strictly for authorized property owners or platform compliance agents.
   - Direct public access to KYC document paths is blocked (SEC-19-01).

---

## 4. Gender-Specific Safety & Privacy Controls

To address personal safety concerns in Indian shared housing:
1. **Female Flatmate Privacy Filter:** Female seekers can restrict their profile and listing visibility exclusively to verified female users.
2. **Anti-Stalking Coordinate Fuzzing:** Public listings do not display exact building numbers or high-precision GPS coordinates; coordinates are fuzzed to ~1.1 km radius (SEC-19-03).
3. **Contact Protection:** Phone numbers and email addresses remain masked until both parties mutually accept a match or confirm an in-person viewing appointment.
4. **Immediate Isolation via Blocking:** Blocking a user immediately severs all chat history, hides search results, and prevents match generation bidirectionally (SEC-19-04).

---

## 5. Grievance Officer & Statutory Disclosures

As mandated by Section 13 of the DPDP Act and Rule 3(2) of the Information Technology (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021:

- **Grievance Officer:** Privacy & Compliance Lead
- **Email:** `grievance@flatmate.platform`
- **Address:** Flatmate Technologies Private Limited, Indiranagar, Bengaluru, Karnataka 560038, India
- **Response SLA:** Acknowledgment within 24 hours; resolution within 15 working days.

---

## 6. Privacy & Compliance Verdict

The platform architecture complies with the core requirements of the DPDP Act 2023, IT Act 2000, and UIDAI guidelines. User consent is affirmative and traceable, data minimization is enforced, and identity documents are securely isolated.

**Privacy & Compliance Gate Status: APPROVED FOR STAGING.**
