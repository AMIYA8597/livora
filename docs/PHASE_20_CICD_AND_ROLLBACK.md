# Phase 20 CI/CD Automation & Rollback Runbook

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** CI/CD Engineer & Release Manager  

---

## 1. Automated Workflow Pipeline Architecture

Four specialized GitHub Actions workflows govern software delivery and environment health:

| Workflow File | Trigger Conditions | Pipeline Execution Stages | Gating Gates |
|---|---|---|---|
| [`.github/workflows/ci.yml`](file:///D:/work/flatmate/.github/workflows/ci.yml) | Push / PR on `main`, `staging`, `develop` | 1. Turborepo Frontend Build & Node Tests<br>2. Python Ruff Lint & Mypy Typecheck<br>3. Backend Pytest with PostGIS & Redis containers | Must achieve 100% test pass and 0 type errors. |
| [`.github/workflows/security.yml`](file:///D:/work/flatmate/.github/workflows/security.yml) | Scheduled weekly + PR changes | 1. Bandit AST Code Scanner<br>2. Pip-audit & Pnpm security audit<br>3. Gitleaks / TruffleHog Secret Pattern Scan<br>4. Security regression test suite | Any High/Critical vulnerability blocks merge. |
| [`.github/workflows/staging-deploy.yml`](file:///D:/work/flatmate/.github/workflows/staging-deploy.yml) | Push to `staging` branch (or manual workflow dispatch) | 1. Remote Cloud Build container packaging<br>2. Push image to Artifact Registry<br>3. Run Alembic DB migrations (`upgrade head`)<br>4. Cloud Run blue-green deploy<br>5. Vercel Staging Deploy | Pre-deploy database healthcheck must succeed. |
| [`.github/workflows/staging-smoke-tests.yml`](file:///D:/work/flatmate/.github/workflows/staging-smoke-tests.yml) | Post-deployment trigger | 1. HTTP Liveness & Readiness Probes (`/health`)<br>2. TLS & HTTPS certificate validation<br>3. `robots.txt` disallow confirmation<br>4. Synthetic Seeker/Owner smoke test | Deployment automatically marks failed if probes fail. |

---

## 2. Zero-Downtime Deployment Protocol

1. **Database Migration Strategy:**
   - Schema migrations must always be backward-compatible (Expand and Contract pattern).
   - Columns are added as nullable or with defaults before application code deploys.
   - Destructive migrations (`DROP COLUMN`, `RENAME COLUMN`) require a multi-phase release process.
2. **Cloud Run Blue-Green / Traffic Splitting:**
   - Cloud Run provisions a new revision (e.g., `flatmate-api-staging-00042`).
   - Built-in container healthcheck executes against `/health`.
   - Once healthy, Cloud Run shifts 100% of traffic instantaneously with zero dropped requests.
3. **Vercel Instant Edge Propagation:**
   - Next.js builds atomic deployments with unique deployment URLs before routing the staging alias.

---

## 3. Instant Rollback Procedures

### Backend Rollback (< 60 Seconds)
If an unhandled exception or latency spike occurs post-deployment:
```bash
# List previous healthy revisions
gcloud run revisions list --service flatmate-api-staging --region asia-south1

# Instantly redirect 100% traffic back to previous healthy revision
gcloud run services update-traffic flatmate-api-staging \
  --region asia-south1 \
  --to-revisions flatmate-api-staging-00041=100
```

### Frontend Rollback (< 30 Seconds)
```bash
# Rollback Vercel staging deployment to previous deployment ID
vercel rollback <previous-deployment-url-or-id> --scope amiyachowdhury04-6543
```

### Database Rollback Runbook
```bash
# Downward migration via Alembic (if backward-compatible migration allowed rollback)
cd apps/api
alembic downgrade -1
```
*Note: If data-modifying migrations were executed, initiate point-in-time recovery (PITR) from the automated Supabase backup snapshot taken immediately before deployment.*
