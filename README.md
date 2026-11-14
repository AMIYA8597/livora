# Flatmate Platform Monorepo

[![CI Status](https://github.com/flatmate/flatmate-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/flatmate/flatmate-platform)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14.2.4-black.svg?logo=next.js)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18.0%20(PostGIS%20%2B%20pgvector)-336791.svg?logo=postgresql)](https://www.postgresql.org)
[![Phase 22](https://img.shields.io/badge/Phase%2022-STAGING%20VERIFIED-brightgreen.svg)](docs/PHASE_22/14_FINAL_INTEGRATION_ASSESSMENT.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An intelligent, full-stack flatmate matching and co-living rental marketplace built with **Next.js 14**, **FastAPI**, **PostgreSQL** (with **PostGIS** geospatial queries and **pgvector** compatibility indexing), **Redis**, and **Supabase**.

---

## Highlights

- **Multi-Factor Lifestyle Matching Engine:** 10-dimension explainable compatibility engine (`v1.0-india-heuristic`) with exact 100% weight sum, dealbreaker enforcement, and reciprocal matching running at **57,000+ evaluations/sec**.
- **Geospatial Discovery:** PostGIS radius search, Haversine distance calculations, and anti-stalking coordinate fuzzing (~1km) in compliance with India's DPDP Act 2023.
- **Flatmate Groups ("Team-Up to Rent"):** Form hunting syndicates with compatible seekers to search, save properties, and vote on shared wishlists.
- **Real-Time Messaging & Presence:** WebSocket protocol with durable PostgreSQL persistence, read cursors, unread counters, and advance deposit scam heuristics.
- **Identity & Trust Verification:** Masked phone numbers, private RLS-restricted document vaults for identity verification, and human moderation queue.
- **Concurrency-Safe Inventory:** Row-level pessimistic locking (`with_for_update`) preventing double-booking of beds and rooms.

---

## Phase 22 Verification & Quality Gate Status

Phase 22 Complete System, Real Supabase Integration, and Security Verification results:
- **Backend Pytest Suite:** **136 Passed, 0 Failed** in 14.42s across 27 test modules (`pytest apps/api/tests -q`)
- **Frontend Test Suite:** **31 Passed, 0 Failed** in 931ms (`pnpm --filter @flatmate/web test`)
- **Total Monorepo Tests:** **167 Passed, 0 Failed**
- **Next.js 14 Production Build:** **32/32 Routes Compiled & Prerendered** cleanly (`pnpm build`)
- **Static Typing & Code Health:** **0 Mypy Errors** across 163 backend source files, **0 Ruff Errors**, **0 ESLint Errors**
- **Design System (`@flatmate/ui`):** 21 accessible WCAG 2.1 AA components
- **Database Schema:** 42 SQLAlchemy domain models, 43 tables in PostgreSQL, 0 column drift, Alembic head `002_messaging_realtime`
- **Row-Level Security:** 6/6 tests passed under non-superuser role `rls_test_user`
- **Live Staging User Journeys:** **7/7 Passed (100%)** (`scripts/e2e_live_staging_workflows.py`)
- **Release Classification:** **`STAGING VERIFIED — READY FOR HOSTED SUPABASE CREDENTIALS`**

---

## Monorepo Structure

```
flatmate/
├── apps/
│   ├── api/                   # FastAPI Python backend (110 endpoints across 20 modules)
│   │   ├── app/               # Core application logic, routers, schemas, services
│   │   ├── migrations/        # Alembic database migrations (001, 002)
│   │   ├── tests/             # Pytest test suite & security regressions
│   │   └── pyproject.toml     # Python dependencies & tool configs
│   └── web/                   # Next.js 14 App Router frontend (32 production routes)
│       ├── app/               # App Router pages and layouts
│       ├── components/        # Reusable UI components
│       ├── lib/               # Centralized API client & utility functions
│       └── tests/             # Client-side integration & unit tests
├── packages/
│   ├── config/                # Shared ESLint, Prettier, and Tailwind configs
│   ├── contracts/             # Shared TypeScript API data transfer contracts (DTOs)
│   └── ui/                    # Shared Design System UI components
├── docs/                      # Architectural specifications & phase audit documentation
│   └── PHASE_22/              # Phase 22 Real Supabase & Security Audit Reports (14 reports)
├── scripts/                   # Staging diagnostics, RLS verification, and E2E suites
├── docker-compose.yml         # Local multi-container orchestration
└── package.json               # Monorepo root package.json (pnpm + Turbo)
```

---

## Quick Start & Verification Drills

### 1. Diagnostics & Validation
```bash
# Validate environment configuration (Zero-Leak)
python scripts/validate_environment_config.py .env.staging

# Probe Supabase and PostgreSQL connectivity
python scripts/test_supabase_connectivity.py

# Reconcile database schema against SQLAlchemy models
python scripts/reconcile_schema.py

# Verify PostgreSQL Row-Level Security policies (Non-superuser)
python scripts/test_rls_policies.py

# Execute live staging multi-actor user journeys (Journeys 1–7)
python scripts/e2e_live_staging_workflows.py

# Benchmark API latency and algorithmic throughput
python scripts/test_performance_benchmarks.py
python scripts/benchmark_api_latency.py
```

### 2. Frontend Test & Build
```bash
# Run unit & security tests
pnpm --filter @flatmate/web test

# Compile production build (32 routes)
pnpm build
```

### 3. Backend Test Suite
```bash
# Run full pytest suite (136 tests)
pytest apps/api/tests -q

# Run security regression suite
pytest apps/api/tests/security/test_security_regressions.py -v
```

---

## Phase 22 Audit Documentation

Complete Phase 22 reports are available in [`docs/PHASE_22/`](docs/PHASE_22/):
- [01 Repository Baseline](docs/PHASE_22/01_REPOSITORY_BASELINE.md)
- [02 Secret & Environment Configuration](docs/PHASE_22/02_SECRET_AND_ENVIRONMENT_CONFIGURATION.md)
- [03 Real Supabase Connectivity Report](docs/PHASE_22/03_REAL_SUPABASE_CONNECTIVITY_REPORT.md)
- [04 Hosted Database Reconciliation](docs/PHASE_22/04_HOSTED_DATABASE_RECONCILIATION.md)
- [05 RLS & Authorization Verification](docs/PHASE_22/05_RLS_AND_AUTHORIZATION_VERIFICATION.md)
- [06 Backend API Verification](docs/PHASE_22/06_BACKEND_API_VERIFICATION.md)
- [07 Frontend Functional Verification](docs/PHASE_22/07_FRONTEND_FUNCTIONAL_VERIFICATION.md)
- [08 AI/ML Implementation & Evaluation](docs/PHASE_22/08_AIML_IMPLEMENTATION_AND_EVALUATION.md)
- [09 Security & Privacy Verification](docs/PHASE_22/09_SECURITY_AND_PRIVACY_VERIFICATION.md)
- [10 Real Supabase E2E Results](docs/PHASE_22/10_REAL_SUPABASE_E2E_RESULTS.md)
- [11 Performance & Reliability](docs/PHASE_22/11_PERFORMANCE_AND_RELIABILITY.md)
- [12 Regression Test Report](docs/PHASE_22/12_REGRESSION_TEST_REPORT.md)
- [13 Known Issues & Blockers](docs/PHASE_22/13_KNOWN_ISSUES_AND_BLOCKERS.md)
- [14 Final Integration Assessment](docs/PHASE_22/14_FINAL_INTEGRATION_ASSESSMENT.md)

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
