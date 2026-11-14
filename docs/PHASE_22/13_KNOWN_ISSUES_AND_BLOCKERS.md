# PHASE 22.13 — Known Issues, Technical Limitations & External Blockers

**Document Version:** 1.0  
**Phase:** 22.13 — Risk Analysis, Gaps & Blocker Documentation  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Software Architect, Application Security Engineer, DevOps Lead  
**Classification:** Operational Risk & Gaps Assessment  

---

## 1. Executive Summary

In adherence to Phase 22 non-negotiable rules:
> "If blocked by credentials, permissions or external configuration, document the exact issue instead of fabricating success."
> "Do not claim successful external integration until it has been tested against the actual external service."

This document inventories every identified blocker, external integration dependency, technical limitation, and manual action required to transition the Flatmate Platform to a hosted Supabase environment.

---

## 2. Active External Integration Blockers

### Blocker 1: Hosted Supabase Project Credentials Awaiting Input
- **Severity:** High (External Integration Blocker)
- **Status:** **BLOCKED (Awaiting Project Owner Input)**
- **Impact:** While the application is 100% verified against local staging infrastructure (port 8001, port 3001, PostgreSQL 18.0), connecting to the actual cloud-hosted Supabase project requires actual project credentials.
- **Missing Parameters:**
  - `SUPABASE_URL` (Hosted project endpoint, e.g., `https://<ref>.supabase.co`)
  - `SUPABASE_ANON_KEY` (Publishable anon JWT)
  - `SUPABASE_SERVICE_ROLE_KEY` (Administrative service key)
  - `SUPABASE_JWT_SECRET` (Supabase Auth JWT verification secret)
  - `DATABASE_URL` / `DATABASE_SYNC_URL` (Direct or connection pooled PostgreSQL URI)
- **Resolution Path:** The project owner must export these variables in the host environment or populate `.env.staging` (which is ignored by Git).

### Blocker 2: Hosted PostGIS & pgvector C-Extension Activation
- **Severity:** Medium (Database Configuration)
- **Status:** **PENDING HOSTED PROVISIONING**
- **Impact:** In the local reference Windows environment, fallback procedural stubs and text domains are utilized. On the hosted Supabase PostgreSQL database, native C-extensions must be enabled prior to applying Alembic migrations.
- **Required SQL Execution in Supabase Dashboard:**
  ```sql
  CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
  CREATE EXTENSION IF NOT EXISTS "pg_trgm";
  CREATE EXTENSION IF NOT EXISTS "postgis";
  CREATE EXTENSION IF NOT EXISTS "vector";
  ```

### Blocker 3: Hosted Supabase Storage Buckets
- **Severity:** Medium (Storage Configuration)
- **Status:** **PENDING BUCKET CREATION**
- **Impact:** The storage abstraction layer requires the following buckets in Supabase Storage:
  1. `staging-property-photos` (Public visibility, authenticated uploads)
  2. `staging-verification-docs` (Private visibility, presigned URL access only)
  3. `flatmate-media-staging` (General application media)

---

## 3. Known Technical Limitations & Design Decisions

### Limitation 1: Algorithmic Recommendation vs Deep Learning
- **Assessment:** Candidate recommendations currently utilize the explainable deterministic 10-dimension compatibility engine (`v1.0-india-heuristic`) with dealbreaker penalties and reciprocal matching.
- **Honest AI Disclosure:** No neural deep learning model or external LLM inference is currently deployed in production. A pluggable ML provider interface (`BaseRecommendationProvider`) exists and falls back gracefully to the deterministic engine.

### Limitation 2: Syntactic Vector Search vs Dense Transformer Retrieval
- **Assessment:** Property search vectors use a 64-dimensional seeded token projection (SHA-256 hash modulo) normalized to unit length.
- **Honest AI Disclosure:** This provides fast, zero-dependency token similarity. It does not perform semantic understanding across synonym terms (e.g., "flat" vs "condo") unless keywords match.

### Limitation 3: Notification Provider in Test-Sink Mode
- **Assessment:** To prevent unintended transactional emails or SMS messages to test accounts during staging verification, `EMAIL_PROVIDER=test-sink` and `MOCK_EMAIL_DELIVERY=True` are enforced. Real customer notifications will require configuring Amazon SES, Twilio, or SendGrid credentials in production.

---

## 4. Required Manual Operator Actions to Deploy Hosted Staging

1. **Supply Hosted Credentials:**
   Export variables securely in the server shell or `.env.staging`:
   ```bash
   export ENVIRONMENT=staging
   export SUPABASE_URL="https://<project-ref>.supabase.co"
   export SUPABASE_ANON_KEY="<anon-key>"
   export SUPABASE_SERVICE_ROLE_KEY="<service-role-key>"
   export SUPABASE_JWT_SECRET="<jwt-secret>"
   export DATABASE_URL="postgresql+asyncpg://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres?ssl=require"
   export DATABASE_SYNC_URL="postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres?ssl=require"
   export STORAGE_TYPE=supabase
   ```
2. **Execute Database Migration:**
   ```bash
   alembic upgrade head
   ```
3. **Run Supabase Connectivity Probe:**
   ```bash
   python scripts/test_supabase_connectivity.py
   ```
4. **Execute Live Staging E2E Suite:**
   ```bash
   python scripts/e2e_live_staging_workflows.py
   ```
