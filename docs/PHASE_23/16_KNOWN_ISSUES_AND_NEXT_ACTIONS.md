# PHASE 23.16 — Known Issues, Technical Limitations & Operator Action Items

**Document Version:** 1.0  
**Phase:** 23.16 — Risk Assessment, Blockers & Operator Next Actions  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Software Architect, Application Security Engineer, DevOps Lead  
**Classification:** Operational Risk Management & Handover Specification  
**Hosted Project URL:** `https://qjwitdovbsfviaepjcul.supabase.co` (Project Ref: `qjwitdovbsfviaepjcul`)  

---

## 1. Executive Summary

In strict compliance with **Non-Negotiable Rule 0**:
> *"If a phase cannot be completed because of network restrictions, missing credentials, provider configuration, external service limitations or permissions, record the exact blocker and continue only with independent tasks that do not depend on it."*  
> *"Never invent successful results."*

This document provides a transparent inventory of all identified operational blockers, environment constraints, and the exact step-by-step manual actions required from the project owner to finalize the cloud database migration.

---

## 2. Identified Operational Blockers & Environmental Constraints

### Blocker 1: Local Network Egress Firewall on PostgreSQL Wire Ports (5432 / 6543)
- **Severity:** Medium (Operational Network Limitation)
- **Status:** **BLOCKED LOCALLY (Empirically Attributed to Local Network Perimeter Firewall)**
- **Diagnostic Proof:**
  - `qjwitdovbsfviaepjcul.supabase.co:443` (HTTPS): **OPEN** (Connected in 42ms).
  - `aws-*-ap-south-1.pooler.supabase.com:6543`: **TIMED OUT** (`WSAEWOULDBLOCK / 10035`).
  - Neutral Control Probe `portquiz.net:5432` / `portquiz.net:6543`: **BLOCKED**; `portquiz.net:443`: **OPEN**.
- **Impact:** Direct `psql` or `asyncpg` wire connections from this local workstation cannot reach the hosted Supabase pooler over ports 5432 or 6543.
- **Resolution Strategy:**
  - The complete static transactional SQL migration script has been generated and validated: `database/migrations/complete_hosted_schema.sql` (35,405 bytes).
  - The project owner can apply this SQL directly in the Supabase Web Dashboard, or execute migrations via a GitHub Actions CI/CD runner where outbound ports 5432/6543 are unblocked.

---

## 3. Known Technical Limitations & Honest AI/ML Disclosures

### Limitation 1: Deterministic 10-Dimensional Heuristic vs Neural LLMs
- **Status:** By Design / Production Baseline.
- **Disclosure:** The compatibility matching engine (`v1.0-india-heuristic`) utilizes a deterministic 10-dimension mathematical model with dealbreaker ceilings ($30\%$). It does NOT run fine-tuned transformers or neural embeddings. A pluggable abstraction interface (`ResilientRecommendationService`) is implemented for future model integration.

### Limitation 2: Fast Token-Projection Search vs Dense Neural Search
- **Status:** By Design / Production Baseline.
- **Disclosure:** The fast property search vector uses a 64-dimensional token projection (SHA-256 modulo hashing), which is a deterministic token transformation rather than a dense vector trained on large text corpora. Real property discovery relies on PostGIS geospatial distance and PostgreSQL trigram keyword matching.

### Limitation 3: Notification Sinks in Staging
- **Status:** By Design / Safety Constraint.
- **Disclosure:** To avoid dispatching accidental SMS or emails to test phone numbers during automated verification, `EMAIL_PROVIDER=test-sink` and `MOCK_EMAIL_DELIVERY=True` are active. Production deployment requires provisioning real Twilio/MSG91 and Amazon SES/SendGrid API keys.

---

## 4. Exact Step-by-Step Operator Actions for Final Production Cutover

To complete the hosted database schema cutover, the project owner should execute the following 3 straightforward steps:

### Step 1: Enable PostgreSQL Extensions in Supabase Dashboard
Open the Supabase Web Dashboard SQL Editor (`https://supabase.com/dashboard/project/qjwitdovbsfviaepjcul/sql`) and run:
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "vector";
```

### Step 2: Apply the Complete Database Schema
Copy and paste the contents of the generated artifact:
`database/migrations/complete_hosted_schema.sql` (35.4 KB)  
into the Supabase SQL Editor and click **Run**.  
This creates all 42 domain tables, foreign key constraints, indexes, and stamps the Alembic version `002_messaging_realtime` in a single transaction.

### Step 3: Apply Row-Level Security (RLS) Policies
In the Supabase SQL Editor, run the contents of:
`database/policies/rls_policies.sql`  
This activates RLS on `profiles`, `applications`, `conversations`, `messages`, `verifications`, and `notifications`.

---

## 5. Recommended Next Phase: Phase 24

**Recommended Scope for Phase 24 (Production Infrastructure, Traffic Ramp & Pilot Launch):**
1. **Cloud Run / ECS Production Deployment:** Deploy containerized backend using immutable Git commit SHA image tags.
2. **Custom Domain & TLS Ingestion:** Bind `api.flatmate.com` and `app.flatmate.com` with automated Cloudflare SSL certificates.
3. **External SMS & Email Integration:** Provision production MSG91 (India DLT registered templates) and Amazon SES credentials.
4. **Controlled User Pilot:** Onboard initial cohort of 50 verified seekers and 10 verified property owners across Koramangala and HSR Layout, Bengaluru.
