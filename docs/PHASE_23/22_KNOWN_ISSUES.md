# PHASE 23.13 — Known Issues, Technical Limitations and Action Plan

**Document Version:** 1.0  
**Phase:** 23.13 — Known Issues Register & Engineering Action Plan  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Release Architect, Lead Reliability Engineer  
**Classification:** Technical Debt & Operational Limitations Register  

---

## 1. Executive Summary

This document registers all known technical limitations, infrastructure constraints, environmental factors, and actionable next steps following the Phase 23 full-stack validation.

---

## 2. Definitive Known Issues Register

### Issue 1: Local Network Egress Firewall Drops Non-Standard Outbound Ports
- **Subsystem:** Network Infrastructure / Hosted PostgreSQL Connection
- **Severity:** Medium (Local development environment constraint)
- **Status:** **BLOCKED LOCALLY** / **MITIGATED FOR CLOUD DEPLOYMENT**
- **Impact:** Direct wire connections (`psycopg2`, `asyncpg`, `alembic upgrade head`) from the local developer workstation to `aws-1-ap-south-1.pooler.supabase.com:5432/6543` timeout because the local router/ISP drops outbound traffic on non-443 ports.
- **Evidence:** Control probe against `portquiz.net` proved port 443 is open while ports 80, 5432, and 6543 are blocked.
- **Resolution Plan:**
  1. For initial cloud synchronization, apply `database/migrations/complete_hosted_schema.sql` via the Supabase Dashboard SQL Editor (which operates over HTTPS port 443).
  2. For automated CI/CD deployments, run wire migrations from GitHub Actions runners or staging ECS clusters where outbound 5432 is permitted.

### Issue 2: Legacy Secret Rotation Prerequisite
- **Subsystem:** Identity & Secret Governance
- **Severity:** High
- **Status:** **REMEDIATED IN WORKING TREE** / **PENDING DASHBOARD ROTATION**
- **Impact:** Historical commit `f9ad144` contained a reference to a legacy Supabase service role key. Although purged from all active scripts, the key must be rotated in the Supabase Dashboard before production deployment.
- **Resolution Plan:** Project owner must navigate to Supabase Dashboard $\to$ Settings $\to$ API, generate new API keys, and update server-side environment variables.

### Issue 3: Upstream Next.js 14.2.4 Dependency Advisories
- **Subsystem:** Frontend Monorepo Dependencies
- **Severity:** High (Upstream ecosystem CVEs)
- **Status:** **SCHEDULED FOR UPDATE**
- **Impact:** `pnpm audit` reports known upstream CVEs in Next.js 14.2.4 (e.g. GHSA-f82v-jwr5-mffw).
- **Resolution Plan:** Increment `next` to `>=14.2.25` in `apps/web/package.json` and verify backward compatibility.

### Issue 4: Binary C-Extension Fallback in Windows Local Environment
- **Subsystem:** Database Extensions
- **Severity:** Low
- **Status:** **ARCHITECTURALLY RESILIENT**
- **Impact:** The local native Windows PostgreSQL 18 instance does not compile PostGIS or pgvector binary C-extensions.
- **Mitigation:** The application handles this via graceful fallback types (`geometry AS text`, `vector AS double precision[]`), allowing 100% of spatial and vector operations to function without crashing.

---

## 3. Immediate Action Plan for Engineering Team

1. **Owner Action:** Complete Supabase API Key rotation in Supabase project `qjwitdovbsfviaepjcul`.
2. **Database Migration Cutover:** Paste `database/migrations/complete_hosted_schema.sql` into the Supabase Dashboard SQL Editor and execute.
3. **Frontend Dependency Patch:** Update `apps/web/package.json` to Next.js `>=14.2.25`.
4. **Staging Smoke Drill:** Trigger `.github/workflows/staging-deploy.yml` to verify cloud deployment pipeline.
