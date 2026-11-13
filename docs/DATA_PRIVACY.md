# Data Privacy & Regulatory Compliance Specification

**Context:** India-First Flatmate Compatibility & Rental Marketplace  
**Compliance Standards:** Digital Personal Data Protection Act (DPDPA 2023), Information Technology Act 2000, Aadhaar Act Data Security Guidelines  

---

## 1. Principles of Personal Data Processing

1. **Lawful, Fair & Transparent Processing:** Personal data is collected strictly upon explicit consent for flatmate matching, tenancy verification, and rental lease facilitation.
2. **Purpose Limitation:** Contact details, government identification, and employer references cannot be shared or sold to third-party telemarketers or brokers without explicit affirmative consent.
3. **Data Minimization:** Only information necessary for identity verification and lifestyle compatibility calculation is stored.
4. **Accuracy & Correction:** Users possess self-service mechanisms to review, update, or correct their personal, professional, and educational profiles.
5. **Storage Limitation:** Government ID copies uploaded for verification are removed or securely scrubbed 90 days after formal verification completion.

---

## 2. Redaction & Sensitive Data Protection Standards

### 2.1 Government Identification (Aadhaar, Passport, Driving License, Voter ID)
- **Strict Prohibitions:** Complete 12-digit Aadhaar numbers must NEVER be stored in plain text. If an Aadhaar copy is reviewed, only masked representations (showing only the last 4 digits `XXXX-XXXX-1234`) are retained in audit logs.
- **Storage Isolation:** All verification documents reside strictly in private storage with presigned temporary URLs expiring within 5 minutes. No public bucket access is permitted under any circumstances.

### 2.2 Location Privacy & Coordinate Masking
- Precise residential coordinates (latitude/longitude) of occupied properties or private rooms are **never exposed** to unverified seekers.
- Public search returns locality-level bounding circles (e.g., "Koramangala 4th Block, Bengaluru" or "Indiranagar, Bengaluru") rather than exact building numbers.
- Exact unit and street address is only unlocked once an appointment viewing is confirmed by the owner/tenant.

### 2.3 Lifestyle & Private Responses
- Individual granular lifestyle answers (e.g., personal habits, hygiene details) are compiled into aggregated score dimensions.
- Explanations display comparative fit categories without revealing confidential personal choices.

---

## 3. Data Subject Rights & Workflows

1. **Right to Access & Portability:** Users can request an export of their account history, submitted applications, and profile data in JSON format via `/api/v1/users/me/export`.
2. **Right to Erasure ("Account Deletion"):** Users can permanently delete their account. Account deactivation marks records inactive immediately, revokes tokens, and schedules full PII purging within 30 days while retaining anonymized transaction logs required by law.
3. **Consent Revocation:** Users can revoke visibility for public search while keeping active private tenancies.
