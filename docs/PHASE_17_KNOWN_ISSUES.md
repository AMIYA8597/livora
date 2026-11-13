# Phase 17 — Known Issues & Environmental Considerations
**Project:** Flatmate Compatibility & Rental Marketplace  
**Phase:** Phase 17 — Integration Audit  
**Date:** November 13, 2026  

---

## 1. Environmental & Infrastructure Considerations

### 1.1 Native Windows PostGIS Extension
- **Observation:** In local native Windows PostgreSQL 18 installations where the PostGIS C-extension binaries (`postgis.dll`) are not compiled or loaded, GeoAlchemy2 SELECT queries wrapped in `ST_AsEWKB` and inserts wrapped in `ST_GeomFromEWKT` require SQL compatibility shim functions.
- **Remediation in Phase 17:** SQL compatibility functions (`st_geomfromewkt`, `st_asewkb`) were created in `flatmate_db`. In addition, the application architecture relies on high-speed pure-Python Haversine calculations (`app/infrastructure/geospatial.py`, benchmarked at 49,687 calculations/sec) for distance calculation and radius filtering.
- **Staging / Production Recommendation:** In Dockerized staging or Supabase production, the official PostGIS extension (`CREATE EXTENSION postgis;`) will be enabled natively in PostgreSQL.

### 1.2 Deprecation Notice: `datetime.utcnow()`
- **Observation:** Python 3.12+ / 3.13 deprecates `datetime.datetime.utcnow()` in favor of `datetime.datetime.now(datetime.UTC)`.
- **Impact:** Emits non-fatal Python deprecation warnings during test execution (`55 warnings in 14s`).
- **Remediation Plan:** Scheduled for Phase 18 codebase hygiene pass.

### 1.3 External Third-Party Services
- **External Storage Buckets:** Live Supabase Cloud S3/Storage bucket operations were executed via mock local file upload endpoints in testing; live cloud bucket upload requires valid `SUPABASE_SERVICE_ROLE_KEY` and remote bucket provisioning.
- **Push Notifications & SMS Gateways:** SMS OTP and WebPush notifications are integrated via service abstractions; actual carrier delivery requires provider API credentials (e.g. Twilio, MSG91) in staging.
