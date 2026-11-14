# PHASE 24.22 — Remaining Blockers & Remediation Action Plan

**Document Version:** 1.0  
**Phase:** 24.18 / 24.22 — Blockers, Root Cause Attribution & Remediation Action Plan  
**Date:** November 15, 2026  
**Auditor Roles:** Principal Infrastructure Architect, Network Reliability Engineer, CISO  
**Classification:** Operational Blockers & Actionable Remediation  
**Project:** Flatmate Compatibility & Rental Marketplace  

---

## 1. Executive Summary

This report catalogues the remaining external blockers, upstream dependencies, and environmental constraints preventing unconditional production deployment, providing clear, actionable remediation procedures for each.

---

## 2. Identified Blockers & Empirical Root Cause Analysis

### Blocker BLK-24-01: Outbound TCP Port 5432 & 6543 Egress Filtering (Workstation Boundary)
- **Classification:** External Network Boundary Restriction
- **Severity:** High (Prevents direct database wire connection from Windows development workstation)
- **Empirical Proof:**
  - `aws-0-ap-south-1.pooler.supabase.com:5432` -> `BLOCKED (TIMEOUT)`
  - `aws-0-ap-south-1.pooler.supabase.com:6543` -> `BLOCKED (TIMEOUT)`
  - Neutral Control: `portquiz.net:443` -> `OPEN / CONNECTED (381ms)`
  - Neutral Control: `portquiz.net:5432` -> `BLOCKED (TIMEOUT)`
  - Neutral Control: `portquiz.net:80` -> `BLOCKED (TIMEOUT)`
- **Root Cause Attribution:** The local router/ISP enforces perimeter firewall egress filtering that drops all outbound TCP SYN packets on ports other than TCP 443. This is an external physical network boundary outside the control of application source code.
- **Actionable Remediation:**
  1. **Option 1 (Instant):** Execute `database/migrations/complete_hosted_schema.sql` via Supabase Dashboard SQL Editor over HTTPS (port 443).
  2. **Option 2 (CI/CD):** Configure GitHub repository secret `STAGING_DATABASE_URL` and run `.github/workflows/hosted-db-migration.yml` on GitHub Actions runners (which have unrestricted port 5432 egress).

---

### Blocker BLK-24-02: Direct Supabase Database Hostname Lacks IPv4 Routing
- **Hostname:** `db.qjwitdovbsfviaepjcul.supabase.co`
- **Severity:** Medium (Informational / Architectural)
- **Empirical Proof:** `getaddrinfo failed [Errno 11001]`
- **Root Cause Attribution:** Supabase direct database hostnames resolve exclusively to IPv6 addresses. In IPv4-only networks, Supabase requires connecting through the Supavisor IPv4 connection poolers (`aws-0-ap-south-1.pooler.supabase.com`).
- **Actionable Remediation:** Always configure `DATABASE_URL` using the pooler domain `aws-0-ap-south-1.pooler.supabase.com` rather than the direct database hostname on IPv4 networks.

---

### Advisory ADV-24-01: Upstream Next.js 14.2.4 Dependency Vulnerabilities
- **Classification:** Upstream Third-Party Dependency
- **Severity:** Medium
- **Empirical Proof:** `pnpm audit --prod` reported 41 advisories in the `apps/web` package tree (e.g. `GHSA-f82v-jwr5-mffw`).
- **Root Cause Attribution:** Next.js 14.2.4 has known upstream advisories that are patched in Next.js 14.2.25+ and Next.js 15.
- **Actionable Remediation:** Schedule an automated upgrade of `next` to `^14.2.25` or `^15.0.0` during the first post-launch minor maintenance sprint.

---

## 3. Post-Blocker Cutover Roadmap

Once **BLK-24-01** is executed via the Supabase Dashboard SQL Editor or GitHub Actions:
1. Interrogate `https://qjwitdovbsfviaepjcul.supabase.co/rest/v1/` to verify all 42 public tables appear in PostgREST OpenAPI definitions.
2. Interrogate `alembic_version` endpoint to confirm revision head `002_messaging_realtime`.
3. Promote release classification to **`READY FOR PRODUCTION`**.
