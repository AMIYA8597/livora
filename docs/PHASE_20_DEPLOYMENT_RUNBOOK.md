# Phase 20 Deployment Runbook & Operational Playbook

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** Senior DevOps & Site Reliability Engineer  

---

## 1. Prerequisites & Tooling Verification

Before executing a deployment or promotion, ensure the following CLI tools are authenticated:
```powershell
# 1. Google Cloud SDK
gcloud auth list
gcloud config set project tradebit-396406
gcloud config set run/region asia-south1

# 2. Vercel CLI
vercel whoami

# 3. GitHub CLI
gh auth status

# 4. Python Environment & Monorepo Dependencies
python --version  # Must be 3.11+
pnpm --version    # Must be 9.0+
```

---

## 2. Step-by-Step Staging Deployment Procedure

### Step 1: Pre-Deployment Validation (Monorepo Quality Gate)
```bash
# Run linting, typechecking, and backend tests
python -m ruff check apps/api
python -m mypy apps/api/app
cd apps/api && python -m pytest tests -q

# Run frontend build and unit tests
pnpm turbo run test
pnpm --filter @flatmate/web build
```

### Step 2: Database Migration Execution
```bash
# Apply pending schema migrations against the staging database using direct port 5432
cd apps/api
alembic upgrade head
```

### Step 3: Seed Synthetic Staging Data (If resetting or initial bootstrap)
```bash
python database/seeds/staging_seed.py
```

### Step 4: Container Build & Backend Cloud Run Deployment
```bash
# Build container image via Google Cloud Build
gcloud builds submit \
  --project tradebit-396406 \
  --tag asia-south1-docker.pkg.dev/tradebit-396406/flatmate-staging/api:latest \
  apps/api

# Deploy image to Cloud Run with Secret Manager bindings
gcloud run deploy flatmate-api-staging \
  --image asia-south1-docker.pkg.dev/tradebit-396406/flatmate-staging/api:latest \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars ENVIRONMENT=staging,PORT=8000 \
  --set-secrets DATABASE_URL=STAGING_DATABASE_URL:latest,SUPABASE_JWT_SECRET=STAGING_JWT_SECRET:latest \
  --memory 512Mi \
  --cpu 1 \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 3
```

### Step 5: Frontend Vercel Staging Deployment
```bash
# Deploy Next.js frontend to Vercel staging
vercel deploy --prod=false apps/web
```

### Step 6: Post-Deployment Smoke Probing
```bash
# Verify API liveness
curl -f https://flatmate-api-staging-<hash>.a.run.app/health

# Verify Web staging robots header
curl -I https://flatmate-web-staging.vercel.app/
# Check for: X-Robots-Tag: noindex, nofollow
```

---

## 3. Disaster Recovery & Emergency Playbooks

### Incident 1: Backend 500 Spike on New Release
1. Run rollback command immediately:
   ```bash
   gcloud run services update-traffic flatmate-api-staging \
     --region asia-south1 \
     --to-revisions <previous-healthy-revision>=100
   ```
2. Inspect Cloud Logging error traces:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit 50
   ```

### Incident 2: Database Connection Pool Exhaustion
1. Check Supabase connection metrics on the dashboard.
2. Confirm FastAPI backend is connecting via transaction pooler port `6543` and NOT direct port `5432`.
3. Restart Cloud Run instances to reset stalled pool connections:
   ```bash
   gcloud run services update flatmate-api-staging --region asia-south1
   ```
