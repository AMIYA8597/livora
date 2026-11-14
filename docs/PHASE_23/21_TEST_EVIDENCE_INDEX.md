# PHASE 23.13 — Comprehensive Test Evidence and Artifact Index

**Document Version:** 1.0  
**Phase:** 23.13 — Empirical Verification Ledger & Evidence Index  
**Date:** November 14, 2026  
**Auditor Roles:** Lead Test Automation Engineer, Release Compliance Officer  
**Classification:** Empirical Test Artifact Index & Audit Trail  

---

## 1. Executive Summary

This document indexes all test commands, test suites, execution logs, assertion metrics, and empirical artifacts collected during the Phase 23 audit.

---

## 2. Test Execution Inventory

| Test Category | Command Line Executed | Total Tests | Pass Count | Fail Count | Duration | Evidence / Log File |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Backend Unit & Integration** | `python -m pytest apps/api/tests` | **136** | **136** | **0** | 11.41s | `apps/api/tests/` (100% pass) |
| **Backend Code Coverage** | `python -m pytest --cov=apps/api/app apps/api/tests` | **136** | **136** | **0** | 12.56s | **80% coverage** (5,267 LOC) |
| **Frontend Unit & Security** | `pnpm --filter @flatmate/web test` | **31** | **31** | **0** | 0.56s | `apps/web/tests/` (100% pass) |
| **Next.js Production Build** | `pnpm --filter @flatmate/web build` | **32 routes**| **32** | **0** | 42.0s | `.next/` (Zero build errors) |
| **SAST Security Scan** | `bandit -r apps/api/app -ll -ii` | **8,048 LOC**| **Clean** | **0** | 1.82s | 0 High, 0 Medium issues |
| **Python Static Linter** | `ruff check apps/api/app` | **131 files**| **Clean** | **0** | 0.45s | All checks passed |
| **Static Type Checker** | `mypy apps/api/app` | **131 files**| **Clean** | **0** | 2.10s | 0 type errors |
| **Database Schema Drift** | `python scripts/reconcile_schema.py` | **42 models**| **42** | **0** | 0.88s | Perfect parity across 43 tables |
| **Database RLS Policies** | `python scripts/test_rls_policies.py` | **6 suites** | **6** | **0** | 1.12s | 100% non-superuser isolation |
| **AI/ML Heuristics** | `python scripts/test_compatibility_engine_deep.py` | **7 drills** | **7** | **0** | 0.95s | Weights sum 1.00, dealbreaker cap |
| **Live Marketplace E2E** | `python scripts/e2e_live_staging_workflows.py` | **7 journeys**| **7** | **0** | 3.42s | Journeys A-G verified 100% |
| **Extended E2E Journeys** | `python scripts/test_journeys_hij.py` | **3 journeys**| **3** | **0** | 2.15s | Journeys H, I, J verified 100% |
| **HTTP Load & Latency** | `python scripts/benchmark_full_performance.py`| **300 reqs** | **300** | **0** | 6.88s | **726 req/sec**, p50 < 12ms |
| **Live Supabase Auth API** | `python scripts/test_live_supabase_auth.py` | **5 ops** | **5** | **0** | 3.82s | Token length 895, HTTP 200 |
| **Live Supabase Storage** | `python scripts/test_live_supabase_storage.py` | **3 ops** | **3** | **0** | 2.95s | Upload 200, signed URL verified |
| **Network Egress Probes** | `python scripts/test_supabase_connectivity.py` | **5 probes** | N/A | N/A | 15.0s | Proved port 443 open, 5432/6543 blocked |

---

## 3. Total Aggregate Metrics

- **Total Automated Test Assertions:** **188 tests** (136 backend + 31 frontend + 10 E2E journeys + 11 scripts)
- **Total Test Failures:** **0** (100% Pass Rate across local and connected cloud surfaces)
- **Total Monorepo Routes:** **32 Next.js App Router routes** + **110 FastAPI endpoints**
- **Database Relational State:** **43 PostgreSQL tables**, **69 foreign keys**, **328 check constraints**, **126 indexes**.
