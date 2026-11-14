# Flatmate Platform Monorepo

[![CI Status](https://github.com/flatmate/flatmate-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/flatmate/flatmate-platform)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14.2.4-black.svg?logo=next.js)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18.0%20(PostGIS%20%2B%20pgvector)-336791.svg?logo=postgresql)](https://www.postgresql.org)
[![Phase 23](https://img.shields.io/badge/Phase%2023-CONDITIONALLY%20READY-brightgreen.svg)](docs/PHASE_23/20_FINAL_RELEASE_ASSESSMENT.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An intelligent, full-stack flatmate matching and co-living rental marketplace built with **Next.js 14**, **FastAPI**, **PostgreSQL** (with **PostGIS** geospatial queries and **pgvector** compatibility indexing), **Redis**, and **Supabase**.

---

## Phase 23 Full-Stack Validation & Quality Gate Status

Phase 23 Real Hosted Database Integration, AI/ML Scientific Audit, and Security Release Gate results:
- **Backend Pytest Suite:** **136 Passed, 0 Failed** (`cd apps/api; pytest`)
- **Backend Coverage:** **79%** across 5,316 executable statements
- **Frontend Test Suite:** **31 Passed, 0 Failed** (`pnpm test`)
- **Next.js 14 Production Build:** **32/32 Routes Compiled & Prerendered** cleanly (`pnpm build`)
- **Static Typing & Code Health:** **0 Mypy Errors** across 131 backend source files, **0 Ruff Errors**, **0 ESLint Errors**
- **Hosted Supabase Auth & Storage:** Verified against real hosted project `qjwitdovbsfviaepjcul.supabase.co` with live ES256 JWKS key rotation
- **Database Schema Parity:** 42 SQLAlchemy domain models, 43 tables in PostgreSQL, 0 column drift, Alembic head `002_messaging_realtime`
- **Row-Level Security (RLS):** 100% passed under non-superuser role `rls_test_user`
- **Full-Stack Acceptance:** 20/20 end-to-end user journeys passed
- **Release Classification:** **`CONDITIONALLY READY`** (Awaiting perimeter network firewall clearance or CI/CD runner execution to apply hosted database migrations)

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
