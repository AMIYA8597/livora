# Known Issues, Operational Observations & Architectural Decisions

**Document:** Defect, Security & Architectural Limitation Tracker  
**Phase:** 20 — Enterprise-Grade Staging Infrastructure, Real Cloud Deployment, CI/CD, Database, Security, Storage, Domain, HTTPS and Complete System Integration  
**Last Updated:** November 14, 2026  
**Status:** **0 Release-Blocking Defects | STAGING ACCEPTED**  

---

## 1. Active Defects & Vulnerabilities Summary
* **Release-Blocking Defects:** **0**
* **Unmitigated High/Critical Vulnerabilities:** **0**
* **Automated Test Suite Status:** **159/159 Passed (128 Backend Pytest + 31 Frontend Node Tests)**.
* **Phase 20 Staging User Journeys:** **8/8 Passed (100%)**.

---

## 2. Operational Observations & Non-Blocking Known Issues

### ISSUE-20-01: Windows Local Docker Daemon Inactive
- **Category:** Environmental
- **Severity:** LOW
- **Description:** On the local development Windows host, the Docker Desktop daemon is inactive. Container builds are executed remotely via Google Cloud Build (`gcloud builds submit`) to Google Artifact Registry.
- **Resolution:** Full automated build & push pipeline configured in `.github/workflows/staging-deploy.yml` and Google Cloud Build.

### ISSUE-20-02: Custom Domain & Registrar Purchase at External Boundary
- **Category:** Infrastructure / Governance
- **Severity:** LOW
- **Description:** Custom domain registration (`livora.in`) requires external payment authorization. Staging environment operates under fully TLS 1.3-encrypted cloud-managed domains (`flatmate-web-staging.vercel.app` and `flatmate-api-staging-<hash>.a.run.app`).
- **Resolution:** Ready for one-click DNS activation upon clearance of domain purchase boundary in Phase 21.

### ISSUE-20-03: `datetime.datetime.utcnow()` Deprecation Warning in SQLAlchemy
- **Category:** Code Health
- **Severity:** TRIVIAL
- **Description:** Python 3.12+ deprecates `datetime.datetime.utcnow()` in favor of `datetime.datetime.now(datetime.UTC)`. Approximately 60 test warnings are emitted during Pytest execution from SQLAlchemy default callables.
- **Resolution:** Zero functional impact; scheduled for factory standardization in Phase 21.

### ISSUE-20-04: Node Typeless Package Warning in Direct Node Tests
- **Category:** Developer Experience
- **Severity:** TRIVIAL
- **Description:** Running `node --test` emits a notice that `apps/web/package.json` does not specify `"type": "module"`.
- **Resolution:** Zero impact on Next.js build; scheduled for module field update in Phase 21.
- **Workaround:** Staging reverse proxy (Cloudflare WAF / Nginx ingress) must enforce edge-level rate-limiting (e.g. 50 requests/sec per IP) prior to public DNS exposure.

### ISSUE-19-05: Horizontal WebSocket Scaling Requires Redis PubSub Adapter
- **Category:** Scalability
- **Severity:** MEDIUM
- **Description:** The current WebSocket connection manager maintains connected client sockets in FastAPI process memory. While sufficient for single-node staging, scaling horizontally to multiple API pods requires Redis PubSub for cross-pod broadcast.
- **Workaround:** Redis broker adapter in `apps/api/app/modules/messaging/broker.py` provides the pub/sub bridge; enable `--workers 1` per container with Redis pubsub in production Helm chart.

---

## 3. Architectural Decision Records (ADRs)

- **ADR-001: Supabase Auth & JWT Verification:** The backend verifies Supabase-issued RS256/HS256 JWT tokens with local verification fallback for offline unit/integration test suites to ensure 100% reproducible tests without external network dependencies.
- **ADR-002: Modular Monolith vs Microservices:** All domains (identity, properties, pg_management, matching, etc.) reside in a single modular monolith to guarantee atomic transactional integrity for room reservations and occupancy management without distributed transaction overhead.
- **ADR-003: PostGIS Spatial Queries & Privacy Fuzzing:** Geographical searches use PostGIS geometry/geography with spatial indexing. Approximate locality coordinates are exposed to public seekers (fuzzed to 2 decimal places, ~1.1km), masking precise residential building coordinates until viewing confirmation or mutual match (SEC-19-03).
- **ADR-004: Concurrency-Safe Bed & Room Occupancy:** Database check constraints and transaction row-locking (`SELECT ... FOR UPDATE`) are enforced to guarantee zero overbooking in PG and shared accommodation (`current_occupants <= max_capacity`, `occupied_beds <= max_beds`).
- **ADR-005: Explainable 10-Dimension Matching Engine:** Matching compatibility is strictly deterministic, transparent, and explainable with weights summing to 100%: Working schedule (15%), Sleep schedule (15%), Budget (15%), Cleanliness (12%), Lifestyle (12%), Noise/Lighting (10%), Guests/Social (7%), Food/Cooking (5%), Domain (5%), Location (4%). Strict dealbreakers cap the overall score at <= 30.0 and supply human-readable conflict justifications.
- **ADR-006: AI/ML Resilient Fallback Architecture:** Optional ML models (vector rerankers, neural content moderators, semantic embeddings) are abstracted behind strict interfaces. If an optional ML model or API key is absent, times out, or throws an error, the system automatically falls back to deterministic heuristic filters and token keyword matching without any service interruption or 500 error.
- **ADR-007: Defense-in-Depth Security:** Employs sliding-window rate limiting, 10MB payload size limits (HTTP 413), RFC 7807 problem details, CSP / HSTS / nosniff security headers, and non-root Docker container execution (`appuser` UID 10001).
