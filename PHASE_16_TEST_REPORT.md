# Phase 16 — Fresh Test Execution Report
## Flatmate Compatibility & Rental Marketplace

**Date of Execution:** 2026-11-13T15:45:00+05:30 to 2026-11-13T15:49:50+05:30  
**Platform:** Windows 11 (Python 3.13.7, Node v24.18.0, pnpm 9.1.0, Turbo 2.11.11)  
**Execution Lead:** Principal QA Lead & Independent Code Auditor  
**Status:** **AUDITED WITH IDENTIFIED GAPS & TYPE DEFECTS**

---

## 1. Test Execution Commands & Results Summary

| Target Subsystem | Command | Execution Status | Duration | Result Summary |
| :--- | :--- | :---: | :---: | :--- |
| **Backend Unit/Mock Tests** | `python -m pytest apps/api/tests -v --tb=short --cache-clear` | **PASSED** | 2.36s | 69 passed, 0 failed (100% pass) |
| **Backend Linting** | `python -m ruff check apps/api` | **PASSED** | 0.45s | 0 errors, 0 warnings |
| **Backend Type Checking** | `python -m mypy apps/api/app --explicit-package-bases --ignore-missing-imports` | **FAILED** | 12.8s | **5 type errors** across 3 files |
| **Contracts Package** | `pnpm --filter @flatmate/contracts test` | **PASSED** | 2.10s | `tsc --noEmit` clean |
| **UI Components Package** | `pnpm --filter @flatmate/ui test` | **PASSED** | 2.45s | `tsc --noEmit` clean |
| **Web App TypeScript** | `pnpm --filter @flatmate/web test` | **PASSED** | 3.80s | `tsc --noEmit` clean |
| **Web App ESLint** | `pnpm --filter @flatmate/web lint` | **PASSED** | 4.20s | 0 errors, 0 warnings |
| **Web App Build** | `pnpm --filter @flatmate/web build` | **PASSED** | 29.5s | 12/12 static/dynamic routes |
| **Monorepo Pipeline** | `pnpm turbo run test build --force` | **RACE DETECTED** | 11.4s | Flaky when run parallel; succeeded when run sequentially |

---

## 2. Detailed Command Outputs

### 2.1 Backend Pytest (Fresh, No Cache)
```text
Command: python -m pytest apps/api/tests -v --tb=short --cache-clear
Exit Code: 0
Output:
platform win32 -- Python 3.13.7, pytest-9.1.1, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: D:\work\flatmate\apps\api
configfile: pyproject.toml
plugins: anyio-4.13.0, Faker-40.36.0, hydra-core-1.3.5, hypothesis-6.168.1, langsmith-0.14.1, locust-2.46.3, asyncio-1.4.0, cov-7.1.0, respx-0.23.1, typeguard-4.6.0
asyncio: mode=Mode.AUTO
collected 69 items

apps\api\tests\test_ai_ml_readiness.py (6 passed)
apps\api\tests\test_applications_appointments.py (4 passed)
apps\api\tests\test_auth.py (2 passed)
apps\api\tests\test_auth_rbac.py (6 passed)
apps\api\tests\test_database_models.py (3 passed)
apps\api\tests\test_e2e_journey.py (2 passed)
apps\api\tests\test_foundation.py (3 passed)
apps\api\tests\test_group_matching.py (4 passed)
apps\api\tests\test_matching.py (3 passed)
apps\api\tests\test_matching_engine_complete.py (4 passed)
apps\api\tests\test_messaging_notifications.py (4 passed)
apps\api\tests\test_owner_tenant_pg_workflows.py (3 passed)
apps\api\tests\test_profiles_lifestyle.py (6 passed)
apps\api\tests\test_properties_domain.py (5 passed)
apps\api\tests\test_search_geospatial.py (5 passed)
apps\api\tests\test_security_hardening.py (5 passed)
apps\api\tests\test_verification_moderation_admin.py (4 passed)

============================= 69 passed in 2.36s ==============================
```

### 2.2 Backend Ruff Linting
```text
Command: python -m ruff check apps/api
Exit Code: 0
Output: All checks passed!
```

### 2.3 Backend Mypy Type Checking
```text
Command: python -m mypy apps/api/app --explicit-package-bases --ignore-missing-imports
Exit Code: 1
Output:
apps\api\app\modules\messaging\service.py:74: error: Incompatible return value type (got "Sequence[Any]", expected "list[Any]")  [return-value]
apps\api\app\modules\properties\service.py:233: error: Incompatible return value type (got "dict[Any, Any] | None", expected "dict[Any, Any]")  [return-value]
apps\api\app\modules\properties\service.py:262: error: Incompatible return value type (got "dict[Any, Any] | None", expected "dict[Any, Any]")  [return-value]
apps\api\app\modules\properties\service.py:279: error: Incompatible return value type (got "dict[Any, Any] | None", expected "dict[Any, Any]")  [return-value]
apps\api\app\infrastructure\storage.py:56: error: Incompatible return value type (got "str | None", expected "str")  [return-value]
Found 5 errors in 3 files (checked 100 source files)
```

### 2.4 Turborepo Monorepo Build
```text
Command: pnpm turbo run test --force && pnpm turbo run build --force
Exit Code: 0
Output:
@flatmate/contracts:test (tsc --noEmit) -> Passed
@flatmate/ui:test (tsc --noEmit) -> Passed
@flatmate/web:test (tsc --noEmit) -> Passed
@flatmate/web:build (next build) -> Compiled successfully (12/12 static/dynamic routes)
```

---

## 3. Test Suite Quality & Gap Analysis

### 3.1 Tests Using Mocks Where Real Integration Tests are Required
- `test_properties_domain.py`, `test_applications_appointments.py`, `test_owner_tenant_pg_workflows.py`, `test_messaging_notifications.py`: All use `mock_db = AsyncMock()`. They test Python conditional branching, but **do not execute real SQL transactions, foreign keys, or database check constraints**.
- `test_e2e_journey.py`: Uses mocked session calls without validating actual database persistence across transitions.

### 3.2 Tests Passing Without Exercising Real Business Logic
- `test_ai_ml_readiness.py`: Tests the isolated `external_services` fallback classes (`ResilientRecommendationService`, `ResilientModerationService`), but these classes are completely unreferenced by the real API routers and services.
- `test_search_geospatial.py`: Validates in-memory Haversine distance and coordinate math, but does not execute PostGIS `ST_DWithin` spatial index queries against PostgreSQL.

### 3.3 Flaky Pipeline Invariants
- `turbo.json`: Running `pnpm turbo run test build --force` triggers a race condition between `web:test` (`tsc --noEmit`) and `web:build` (`next build`), because `next build` cleans and regenerates `.next/types` concurrently while `tsc` is reading them.

### 3.4 Missing Critical Tests
1. Real PostgreSQL database connection and Alembic migration upgrade/downgrade execution.
2. Concurrent occupancy tests (verifying row locking on simultaneous bed assignment).
3. IDOR security tests for `GET /api/v1/applications/{id}` and `GET /api/v1/appointments/{id}`.
4. Token revocation tests (verifying revoked JWTs fail authentication).
5. PostGIS geospatial query performance with spatial index (`GIST`).
