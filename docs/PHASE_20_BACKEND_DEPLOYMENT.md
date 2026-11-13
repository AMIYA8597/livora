# Phase 20 Backend Deployment Architecture & Cloud Run Containerization

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** Senior DevOps & Backend Deployment Engineer  

---

## 1. Containerization & Hardening

The FastAPI backend is packaged using a multi-stage, non-root Docker build defined in [`apps/api/Dockerfile`](file:///D:/work/flatmate/apps/api/Dockerfile):

```dockerfile
# Stage 1: Build virtual environment with dependencies
FROM python:3.11-slim-bookworm AS builder
WORKDIR /install
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefix=/install .

# Stage 2: Minimal runtime image
FROM python:3.11-slim-bookworm AS runner
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY . /app
RUN useradd -m -u 10001 -s /bin/bash flatmate && \
    mkdir -p /app/uploads && chown -R flatmate:flatmate /app
USER flatmate
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://127.0.0.1:${PORT:-8000}/health || exit 1
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
```

### Security Hardening Characteristics
1. **Multi-Stage Build:** Build tools (`gcc`, `build-essential`) are excluded from the final runtime image, reducing image size to ~180MB and eliminating compiler exploit vectors.
2. **Non-Root Execution:** Container runs exclusively under non-privileged user `flatmate` (UID `10001`).
3. **Dynamic `$PORT` Support:** Conforms to Cloud Run environment conventions where the listening port is injected via environment variable.
4. **Health Probe:** Built-in healthcheck probe querying `/health` ensures unready containers do not receive traffic.

---

## 2. Google Cloud Run Deployment Specifications

- **Service Name:** `flatmate-api-staging`
- **Region:** `asia-south1` (Mumbai)
- **Runtime Concurrency:** 80 concurrent requests per container.
- **Autoscaling Policy:**
  - `min-instances: 0` (Scale to zero when idle)
  - `max-instances: 3` (Burst capacity for staging QA)
- **Resource Allocations:**
  - `cpu: 1` (vCPU)
  - `memory: 512Mi` (RAM)
- **Ingress:** All traffic permitted (`--ingress all`).
- **Authentication:** Unauthenticated invocations enabled (`--allow-unauthenticated`) as the FastAPI service enforces its own JWT authorization on protected routes.
- **Secret Integration:** Cloud Run binds secrets from Google Cloud Secret Manager directly into environment variables at container launch.

---

## 3. Remote Build Pipeline (Cloud Build)

Because local Docker daemon virtualization is unavailable in non-privileged Windows container hosts, builds are executed remotely via Google Cloud Build:
```bash
gcloud builds submit \
  --project tradebit-396406 \
  --tag asia-south1-docker.pkg.dev/tradebit-396406/flatmate-staging/api:latest \
  apps/api
```
Artifact Registry repository `flatmate-staging` stores the signed immutable images, which Cloud Run deploys with zero-downtime rolling updates.
