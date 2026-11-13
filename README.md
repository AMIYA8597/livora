# Flatmate Platform Monorepo

[![CI Status](https://github.com/flatmate/flatmate-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/flatmate/flatmate-platform)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14.2.4-black.svg?logo=next.js)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18.0%20(PostGIS%20%2B%20pgvector)-336791.svg?logo=postgresql)](https://www.postgresql.org)
[![Quality Gate](https://img.shields.io/badge/Phase%2020-STAGING%20ACCEPTED-brightgreen.svg)](docs/PHASE_20_FINAL_REPORT.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An intelligent, full-stack flatmate matching and co-living rental platform built with **Next.js 14**, **FastAPI**, **PostgreSQL** (with **PostGIS** geospatial queries and **pgvector** lifestyle compatibility scoring), **Redis**, and **Supabase**.

---

## Highlights

- **Multi-Factor Lifestyle Matching Engine:** Combines pgvector cosine similarity with 10-dimension category scoring (sleep schedule, cleanliness, social battery, habits, diet, and pet tolerance) running at **58,000+ evaluations/sec**.
- **Geospatial Discovery:** PostGIS-powered radius searches, commute-time calculations, and anti-stalking coordinate fuzzing (~1.1 km) for public seekers.
- **Flatmate Groups ("Team-Up to Rent"):** Form hunting syndicates with compatible seekers to search and apply for entire properties together.
- **Real-Time Messaging & Presence:** Asynchronous WebSockets powered by Redis Pub/Sub for direct and group chat, typing indicators, and read receipts.
- **Identity & Trust Verification:** Multi-tier verification pipeline conforming to India's DPDP Act 2023 with masked Aadhaar storage (`XXXX-XXXX-1234`) and private RLS-restricted document vaults.
- **End-to-End Rental Applications:** Structured application tracking from draft submission to landlord review, interview scheduling, and digital lease proposals.
- **Concurrency-Safe Inventory:** Row-level pessimistic locking (`with_for_update`) prevents double-booking of beds and rooms.

---

## Quality Assurance & Release Status

Phase 18 Complete Product Experience & Finalization verification completed:
- **Backend Pytest Suite:** **136 Passed, 0 Failed** (`pytest apps/api/tests -q`)
- **Phase 18 Acceptance Journeys (A–H):** **8 Passed, 0 Failed** (`apps/api/tests/test_phase18_e2e_acceptance.py`)
- **Frontend Test Suite:** **31 Passed, 0 Failed** (`pnpm --filter @flatmate/web test`)
- **Frontend Routes:** **32/32 Routes Compiled & Statically/Dynamically Prerendered** in Next.js 14
- **Static Typing & Code Health:** **0 Mypy Errors** (131 files), **0 Ruff Errors**, **0 ESLint Errors**
- **Design System (`@flatmate/ui`):** 21 accessible WCAG 2.1 AA components in Forest Green/Charcoal palette
- **Database Schema:** PostgreSQL at Alembic Head (`002_messaging_realtime`)
- **Release Classification:** **`PRODUCTION READY & COMMERCIALLY USABLE`**

---

## Monorepo Structure

```
flatmate/
├── apps/
│   ├── api/                   # FastAPI Python backend (98 endpoints across 20 modules)
│   │   ├── app/               # Core application logic, routers, schemas, services
│   │   ├── tests/             # Pytest test suite & security regressions
│   │   └── pyproject.toml     # Python dependencies & tool configs
│   └── web/                   # Next.js 14 App Router frontend (21 production routes)
│       ├── app/               # App Router pages and layouts
│       ├── components/        # Reusable UI components
│       ├── lib/               # Centralized API client & utility functions
│       └── tests/             # Client-side integration & unit tests
├── packages/
│   ├── config/                # Shared ESLint, Prettier, and TypeScript configs
│   ├── contracts/             # Shared TypeScript API data transfer contracts (DTOs)
│   └── ui/                    # Shared Design System UI components
├── docs/                      # Phase 19 QA, Security & Architecture Documentation
├── docker-compose.yml         # Staging multi-container orchestration
└── package.json               # Monorepo root package.json (pnpm + Turbo)
```

---

## Quick Start & Local Execution

### 1. Prerequisites
- Node.js $\ge 20$ and `pnpm` $\ge 9.1.0$
- Python $\ge 3.11$ (Tested on Python 3.13)
- PostgreSQL $\ge 16$ with `postgis` and `vector` extensions

### 2. Frontend Setup
```bash
# Install dependencies
pnpm install

# Run type checks and unit tests
pnpm turbo run test

# Run linter
pnpm turbo run lint

# Start development server
pnpm turbo run dev
```

### 3. Backend Setup
```bash
# Navigate to API directory
cd apps/api

# Install dependencies in virtual environment
pip install -e .[dev]

# Apply database migrations
python -m alembic upgrade head

# Run backend test suite
python -m pytest tests/ -v

# Run security regressions suite
python -m pytest tests/security/test_security_regressions.py -v

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

---

## Documentation & Phase Reports

Detailed specifications and architectural decisions are documented under /docs:
- [Phase 17.2 Execution Tracker](docs/PHASE_17_2_EXECUTION_TRACKER.md)
- [Phase 17.2 Baseline Remediation Report](docs/PHASE_17_2_BASELINE_REMEDIATION_REPORT.md)
- [Phase 17.2 Frontend Module Report](docs/PHASE_17_2_FRONTEND_MODULE_REPORT.md)
- [Phase 17.2 API Coverage Matrix](docs/PHASE_17_2_API_COVERAGE_MATRIX.md)
- [Phase 17.2 Storage Security Report](docs/PHASE_17_2_STORAGE_SECURITY_REPORT.md)
- [Phase 17.2 Security Report](docs/PHASE_17_2_SECURITY_REPORT.md)
- [Phase 17.2 E2E Test Report](docs/PHASE_17_2_E2E_TEST_REPORT.md)
- [Phase 17.2 Performance Report](docs/PHASE_17_2_PERFORMANCE_REPORT.md)
- [Phase 17.2 Known Issues](docs/PHASE_17_2_KNOWN_ISSUES.md)

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
