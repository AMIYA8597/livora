# PHASE 23.9 — Privacy Assessment and Indian DPDP Act 2023 Review

**Document Version:** 1.0  
**Phase:** 23.9 — Data Privacy Architecture, PII Governance & DPDP Review  
**Date:** November 14, 2026  
**Auditor Roles:** Data Privacy Officer (DPO), Regulatory Compliance Analyst  
**Classification:** Privacy Impact Assessment & Statutory Compliance Review  
**Applicable Legal Framework:** Digital Personal Data Protection Act, 2023 (DPDP Act, India)  

---

## 1. Executive Summary

This privacy assessment audits personal data flows, data minimization, consent management, storage isolation, and user privacy rights across the Flatmate platform under the **Digital Personal Data Protection Act, 2023 (DPDP Act)**.

In strict compliance with **Non-Negotiable Rule 0**:
- **Statutory Transparency:** We do NOT claim unconditional legal immunity or certified legal compliance merely because masking algorithms or consent checkboxes exist. Legal compliance requires ongoing corporate governance, registered Data Fiduciary policies, and independent legal counsel review.
- **Data Minimization (Aadhaar Avoidance):** The platform strictly avoids collecting Indian National Aadhaar numbers to prevent UIDAI regulatory exposure, biometric risks, and statutory penalties under the Aadhaar Act. Alternate identity proofs (Driving License, Passport, Voter ID) are utilized.
- **Redaction by Design:** Exact residential addresses and direct phone numbers are masked by default and disclosed only upon mutual match or confirmed viewing appointment.

---

## 2. Personal Data Inventory and Classification

| Data Category | Examples Collected | Sensitivity | Storage Location | Access Policy / Protection |
| :--- | :--- | :---: | :--- | :--- |
| **Identity & Contact** | Full name, email, phone number | High | `users` table | Phone number masked (+91 98****1234) until mutual match. |
| **KYC / Verification** | Passport / Voter ID / DL image | Critical | Private bucket `verification-docs` | Non-public; ES256 signed URLs (max 3600s); admin audit logged. |
| **Locality & Address** | House number, street, pincode | High | `properties` table | Public view shows locality/city only. Exact address masked. |
| **Lifestyle & Habits** | Diet, smoking, sleep habits, chores | Medium | `lifestyle_profiles` | Visible on public discovery cards for matching purposes. |
| **Private Chat** | Direct messages, shared media | High | `messages`, `attachments` | Restricted strictly to conversation participants and RLS. |
| **Payment History** | Transaction ID, tier, currency | High | `payments` table | Payment processor tokens only. No credit card / CVV stored. |

---

## 3. Data Protection Safeguards & Masking Heuristics

### 3.1 Exact Address Masking
- Evaluated in `scripts/run_security_audit.py::Test 5`:
- Unconfirmed visitors and general search results receive masked address representations:
  ```json
  "address": "[Exact address protected - revealed upon confirmed visit]"
  ```
- The exact building number and street name are revealed strictly after the property owner approves a scheduled viewing appointment (`AppointmentStatus.CONFIRMED`).

### 3.2 Phone Number & Communication Protection
- Phone numbers are masked in all public API responses:
  ```
  Original: "+91 9876543210" -> Masked: "+91 98765****0"
  ```
- In-app WebSocket chat eliminates the requirement for seekers and owners to share raw personal phone numbers during initial discovery.

### 3.3 Aadhaar Collection Avoidance Strategy
- The platform explicitly disallows uploading Aadhaar cards. Verification documentation instructions mandate government photo IDs that carry zero biometric or UIDAI restrictions (e.g. Passport, Election Voter ID, Driving License).

### 3.4 Zero PII in Server Logs
- Logging middleware in `apps/api/app/core/logging.py` redacts:
  - Authorization Bearer tokens
  - Password fields (`password`, `confirm_password`, `old_password`)
  - Full phone numbers and email query strings

---

## 4. Digital Personal Data Protection Act 2023 (DPDP) Rights

1. **Right to Access & Data Portability:**
   - Supported via `GET /api/v1/users/me` and JSON profile export endpoint. Users can download their complete profile, lifestyle traits, and application history.
2. **Right to Correction & Erasure (Right to be Forgotten):**
   - Users can update personal traits at `/profile`.
   - Account deletion triggers a cascade anonymization: PII is purged, user status marked `deactivated`, and identity documents deleted from cloud storage.
3. **Notice & Purpose Limitation:**
   - Clear privacy notice presented during registration (`apps/web/app/privacy/page.tsx`). Consent logs recorded with timestamps.
   - Retraction of consent immediately halts recommendation processing.
