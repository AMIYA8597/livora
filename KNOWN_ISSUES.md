# Known Issues & Architectural Decisions

**Document:** Defect & Architectural Limitation Tracker  
**Last Updated:** 2026-11-13  
**Status:** **0 Release-Blocking Defects**  

---

## 1. Active Defects
*No release-blocking defects currently open. All 69 automated regression tests passing cleanly.*

---

## 2. Architectural Decisions & Scope Boundaries
- **ADR-001: Supabase Auth & JWT Verification:** The backend verifies Supabase-issued RS256/HS256 JWT tokens with local verification fallback for offline unit/integration test suites to ensure 100% reproducible tests without external network dependencies.
- **ADR-002: Modular Monolith vs Microservices:** All domains (identity, properties, pg_management, matching, etc.) reside in a single modular monolith to guarantee atomic transactional integrity for room reservations and occupancy management without distributed transaction overhead.
- **ADR-003: PostGIS Spatial Queries & Privacy Fuzzing:** Geographical searches use PostGIS geometry/geography with spatial indexing. Approximate locality coordinates are exposed to public seekers (fuzzed to 2 decimal places, ~1.1km), masking precise residential building coordinates until viewing confirmation or mutual match.
- **ADR-004: Concurrency-Safe Bed & Room Occupancy:** Database check constraints and transaction row-locking (`SELECT ... FOR UPDATE`) are enforced to guarantee zero overbooking in PG and shared accommodation (`current_occupants <= max_capacity`, `occupied_beds <= max_beds`).
- **ADR-005: Explainable 10-Dimension Matching Engine:** Matching compatibility is strictly deterministic, transparent, and explainable with weights summing to 100%: Working schedule (15%), Sleep schedule (15%), Budget (15%), Cleanliness (12%), Lifestyle (12%), Noise/Lighting (10%), Guests/Social (7%), Food/Cooking (5%), Domain (5%), Location (4%). Strict dealbreakers cap the overall score at <= 30.0 and supply human-readable conflict justifications.
- **ADR-006: AI/ML Resilient Fallback Architecture:** Optional ML models (vector rerankers, neural content moderators, semantic embeddings) are abstracted behind strict interfaces. If an optional ML model or API key is absent, times out, or throws an error, the system automatically falls back to deterministic heuristic filters and token keyword matching without any service interruption or 500 error.
- **ADR-007: Defense-in-Depth Security:** Employs sliding-window rate limiting, 10MB payload size limits (HTTP 413), RFC 7807 problem details, CSP / HSTS / nosniff security headers, and non-root Docker container execution (`flatmate` UID 10001).
