# Phase 17.2 Known Issues & Operational Considerations

**Project:** Flatmate Compatibility & Rental Marketplace  
**Phase:** Phase 17 — Frontend–Backend Integration  
**Stage:** Phase 17.2 — Baseline Remediation & Completion  
**Timestamp:** 2026-11-13  
**Status:** DOCUMENTED & MONITORED  

---

## 1. Overview

While all 14 baseline defects, missing modules, security vulnerabilities, and typing issues have been resolved, this document catalogues operational boundaries, environment-specific behaviors, and prerequisites for subsequent deployment phases.

---

## 2. Operational Considerations & Environment Constraints

### 2.1 File Storage Provider Configuration
- **Current State:** Default development environment uses `LocalStorageProvider` (`uploads/` directory on disk).
- **Production Requirement:** Setting `STORAGE_BACKEND=supabase` or `STORAGE_BACKEND=s3` requires configuring `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` or AWS S3 credentials in the environment.
- **Handling:** `StorageService` automatically falls back to `LocalStorageProvider` if cloud credentials are absent during local development, preventing startup crashes.

### 2.2 Password Reset Token Delivery (Email / SMS)
- **Current State:** In `development` and `test` environments (`ENVIRONMENT=development` or `ENVIRONMENT=test`), `POST /api/v1/auth/forgot-password` returns the generated JWT reset token in the JSON response body (`res["reset_token"]`). This enables seamless automated testing and local developer workflows without an SMTP mail server.
- **Production Requirement:** In production (`ENVIRONMENT=production`), `res["reset_token"]` is omitted, and tokens are dispatched exclusively via transactional email (SendGrid/Postmark) or SMS OTP (Fast2SMS/Twilio).

### 2.3 PostGIS Map Geocoding & Tile Rendering
- **Current State:** Map display in Next.js uses OpenStreetMap public tiles. Exact property coordinates are masked to ~1.1 km for public users under DPDP compliance.
- **Production Requirement:** High-traffic production deployments should configure a dedicated Mapbox or Google Maps API key (`NEXT_PUBLIC_MAPBOX_TOKEN`) with domain referrers configured to avoid rate limits on public OSM tiles.

### 2.4 WebSocket Real-Time Scaling
- **Current State:** Real-time messaging uses the in-memory WebSocket broker (`apps/api/app/modules/messaging/websocket.py`).
- **Production Requirement:** When running multiple FastAPI container replicas behind an Application Load Balancer, Redis PUB/SUB must be enabled by setting `REDIS_URL` in production to broadcast messages across all active worker nodes.

---

## 3. Scope Boundaries & Next Phase Readiness

- **Phase 17.2 Scope Completed:** All baseline defects eliminated, missing routes implemented, components integrated, full E2E journeys validated against real database.
- **Phase 18 (Release Candidate Staging):** Ready for initiation upon user review and approval. No Phase 18 deployment activities have been executed in this phase.
