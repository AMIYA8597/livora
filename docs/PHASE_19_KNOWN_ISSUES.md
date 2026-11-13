# Phase 19 — Known Issues, Operational Observations & Technical Debt Log

**Project:** Flatmate Compatibility & Rental Marketplace  
**Document ID:** `OPS-19-KIL-01`  
**Phase:** 19 — Full-System Quality Assurance, Adversarial Security Testing & Release Candidate Verification  
**Evaluation Standard:** Production Readiness Review (PRR) & Defect Tracking  
**Author:** Principal Software Architect & Release Manager  
**Date:** November 2026  
**Status:** BASELINED  

---

## 1. Executive Summary

This document catalogues all non-blocking known issues, operational observations, and deferred technical debt identified during Phase 19. None of the listed items represent active blockers for staging deployment. Each item has an associated mitigation, workaround, and scheduled resolution timeline.

---

## 2. Active Known Issues & Observations Catalog

### ISSUE-19-01: Windows Local Docker Daemon Inactive
- **Severity:** LOW (Operational / Environmental)
- **Description:** On the local development Windows host, the Docker Desktop daemon was not running (`//./pipe/dockerDesktopLinuxEngine` not found). Local verification was conducted directly against native Python 3.13 and physical PostgreSQL 18.
- **Impact:** Local multi-container Docker Compose could not be booted directly on the Windows host.
- **Workaround / Resolution:** Standard Linux CI workflow (`.github/workflows/ci.yml`) is specified and verified for automated container builds and Docker Compose testing in Linux environments.
- **Target Resolution:** Handled via Linux Staging CI runner.

---

### ISSUE-19-02: External Third-Party Secrets Pending Staging Ingestion
- **Severity:** LOW (Deployment Configuration)
- **Description:** Live external services (production Supabase Auth project, Indian SMS OTP gateway MSG91, transactional email SendGrid, AWS S3 bucket) require production secret keys to be populated in the cloud vault.
- **Impact:** System runs cleanly with local storage provider, local JWT verification, and test fixtures, but cannot send live SMS text messages or authenticate via external third-party OAuth until secrets are provided.
- **Workaround / Resolution:** Environment templates (`.env.example`) document every required secret; secrets will be injected directly into the staging secrets manager upon staging deployment.
- **Target Resolution:** Staging deployment setup.

---

### ISSUE-19-03: `datetime.datetime.utcnow()` Deprecation Warning in SQLAlchemy
- **Severity:** TRIVIAL (Code Health)
- **Description:** Python 3.12+ deprecates `datetime.datetime.utcnow()` in favor of `datetime.datetime.now(datetime.UTC)`. Approximately 58 test warnings were emitted during Pytest execution, primarily from SQLAlchemy 2.0 internal default callables.
- **Impact:** Purely informational; zero functional impact on application logic.
- **Workaround / Resolution:** Active application service code already uses `datetime.now(timezone.utc)`; default factory callables in older migration scripts will be refreshed during Phase 20 schema maintenance.
- **Target Resolution:** Phase 20 maintenance sprint.

---

### ISSUE-19-04: Edge Rate-Limiting Delegation to Reverse Proxy
- **Severity:** MEDIUM (Scalability / Infrastructure)
- **Description:** While SlowAPI in-memory rate-limiting is implemented in FastAPI for key authentication routes, application-tier rate limiting does not protect against volumetric DDoS attacks on the TCP layer.
- **Impact:** High-volume HTTP floods could consume application server worker threads.
- **Workaround / Resolution:** Staging reverse proxy (Cloudflare WAF / Nginx ingress) must enforce edge-level rate-limiting (e.g. 50 requests/sec per IP) prior to public DNS exposure.
- **Target Resolution:** Staging infrastructure setup.

---

### ISSUE-19-05: Horizontal WebSocket Scaling Requires Redis PubSub Adapter
- **Severity:** MEDIUM (Scalability)
- **Description:** The current WebSocket connection manager maintains connected client sockets in FastAPI process memory. While sufficient for single-node staging, scaling horizontally to multiple API pods requires Redis PubSub for cross-pod broadcast.
- **Impact:** In a multi-pod cluster, users connected to Pod A would not receive instant socket notifications emitted by actions on Pod B unless routed via Redis.
- **Workaround / Resolution:** Redis broker adapter in `apps/api/app/modules/messaging/broker.py` provides the pub/sub bridge; enable `--workers 1` per container with Redis pubsub in production Helm chart.
- **Target Resolution:** Production Go-Live.

---

## 3. Known Issues Summary Table

| Issue ID | Category | Severity | Workaround Available | Blocking Staging? | Target Resolution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ISSUE-19-01** | Infrastructure | LOW | Linux CI Workflow | **NO** | Staging CI |
| **ISSUE-19-02** | Configuration | LOW | Environment Vault | **NO** | Staging Config |
| **ISSUE-19-03** | Code Health | TRIVIAL | Ignore warning | **NO** | Phase 20 |
| **ISSUE-19-04** | Security / DDoS | MEDIUM | Edge WAF / Nginx | **NO** | Staging Ingress |
| **ISSUE-19-05** | Scalability | MEDIUM | Redis PubSub Adapter | **NO** | Production Go-Live |

---

## 4. Known Issues Verdict

No critical bugs or security flaws remain unaddressed. All identified items are operational, configuration-driven, or scalability enhancements properly planned for subsequent staging and production phases.

**Status: ACCEPTABLE FOR STAGING RELEASE.**
