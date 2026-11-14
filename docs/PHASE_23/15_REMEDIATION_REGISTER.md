# PHASE 23.9 — Security and Engineering Remediation Register

**Document Version:** 1.0  
**Phase:** 23.9 — Vulnerability Tracking, Prioritization & Remediation Register  
**Date:** November 14, 2026  
**Auditor Roles:** Application Security Lead, Engineering Operations Manager  
**Classification:** Remediation Register & Risk Governance  

---

## 1. Executive Summary

This register catalogs all security, dependency, architecture, and code hygiene findings identified during the Phase 23 audit, tracking their severity, remediation status, action plan, and ownership.

---

## 2. Definitive Remediation Register

| Issue ID | Finding Description | Subsystem | Severity | Status | Action Plan / Remediation Details |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **SEC-23-01** | Legacy Supabase service role key referenced in 3 test scripts in commit `f9ad144` | Secret Governance | **HIGH** | **REMEDIATED (CODE)** / **PENDING ROTATION** | All scripts refactored to read from `os.getenv()`. Project owner must rotate keys in Supabase Dashboard before production launch. |
| **SEC-23-02** | Upstream Next.js 14.2.4 security advisories identified in `pnpm audit` | Frontend Runtime | **HIGH** | **SCHEDULED** | Upgrade `next` package to `>=14.2.25` in `apps/web/package.json` following staging validation. |
| **INF-23-01** | Outbound TCP ports 5432/6543 dropped by local network egress firewall | Network Connectivity| **MEDIUM** | **MITIGATED** | Staging and production migrations routed via GitHub Actions cloud runner and Supabase Dashboard SQL Editor (`complete_hosted_schema.sql`). |
| **DEP-23-01** | Python `datetime.utcnow()` deprecation warnings in test suites | Backend Code | **LOW** | **IN PROGRESS** | Deprecated calls scheduled for refactoring to `datetime.now(timezone.utc)`. |
| **DEP-23-02** | Supabase Python client deprecation warning for `timeout`/`verify` parameters | Storage Client | **LOW** | **IN PROGRESS** | Configure HTTP client settings directly in `httpx` transport client. |
| **DOC-23-01** | Historical documentation referred to "Deep Learning NLP" for compatibility | Documentation | **LOW** | **REMEDIATED** | Corrected all technical documentation to accurately describe the deterministic 10-dimension weighted heuristic. |
| **DOC-23-02** | Historical documentation mentioned Prisma ORM | Documentation | **LOW** | **REMEDIATED** | Reaffirmed SQLAlchemy 2.x and Alembic as the sole ORM and migration authority. |

---

## 3. Risk Acceptance & Release Gate Policy

- **Critical & High Blockers:** Must be remediated or verified non-exploitable before any production release.
- **Key Rotation Prerequisite:** In strict compliance with security rules, the project owner's verification of rotated credentials is the prerequisite gate for production deployment.
