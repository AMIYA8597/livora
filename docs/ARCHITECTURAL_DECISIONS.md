# Architectural Decision Records (ADRs)
## Flatmate Compatibility & Rental Marketplace

---

### ADR 001: Modular Monolith over Microservices
- **Status:** Accepted
- **Context:** The system handles diverse interconnected rental domains (identity, profiles, properties, rooms, beds, matching, applications, messaging, moderation). Distributed microservices introduce operational overhead, distributed transaction failures, network latency, and unnecessary hosting costs.
- **Decision:** Implement a modular monolith in FastAPI. Maintain clean layered architecture (API -> Services -> Domain Models -> Infrastructure) with explicit dependency injection, allowing future service extraction if necessary.

---

### ADR 002: Technology Stack (Python 3.13 + FastAPI + SQLAlchemy 2.x)
- **Status:** Accepted
- **Context:** High-performance asynchronous REST endpoints, mathematical vector manipulation, and strict type safety are required.
- **Decision:** Use Python 3.13 with FastAPI and Pydantic v2 for request/response serialization, alongside SQLAlchemy 2.x with `asyncpg` for PostgreSQL connection management and transaction isolation.

---

### ADR 003: Authentication & Identity Management
- **Status:** Accepted
- **Context:** The platform requires secure multi-role RBAC (Students, Working Professionals, Owners, Tenants, PG Operators, Admins) and seamless third-party auth.
- **Decision:** Integrate Supabase Auth JWT validation as the primary identity provider, supported by a native JWT claim validator and bcrypt (work factor 12) for local test environments and provider-independent deployments.

---

### ADR 004: Geospatial & Vector Search via PostgreSQL Extensions
- **Status:** Accepted
- **Context:** Accommodation search requires distance-based proximity queries (radius, bounding box), while flatmate matching benefits from dense embedding similarity.
- **Decision:** Consolidate data persistence into PostgreSQL with PostGIS (`ST_DWithin`, `ST_Distance`) and `pgvector` (64-dimensional embeddings), avoiding external specialized search engines (Elasticsearch/Pinecone) to keep infrastructure free-first and operationally simple.

---

### ADR 005: Explainable 10-Factor Compatibility Algorithm
- **Status:** Accepted
- **Context:** Roommate compatibility requires transparent, trustable, and explainable scoring rather than black-box AI outputs.
- **Decision:** Implement a deterministic 10-dimension heuristic compatibility engine with exact 100% weights (Work 15%, Sleep 15%, Budget 15%, Cleanliness 12%, Lifestyle 12%, Noise 10%, Guests 7%, Food 5%, Domain 5%, Location 4%). Hard dealbreakers cap compatibility at $\le 30.0$ and produce human-readable conflict justifications.

---

### ADR 006: Indian Accommodation Inventory Model
- **Status:** Accepted
- **Context:** Indian rental markets feature complex configurations: 1RK, 1BHK, 2BHK, 3BHK, PGs with floor-level gender separation, meal plans, private rooms, and shared bed-by-bed bookings.
- **Decision:** Model accommodation hierarchically: `Property` -> `Room` -> `Bed`. Enforce database-level and service-level capacity invariants: `current_occupants <= max_capacity` and `occupied_beds <= max_beds`.

---

### ADR 007: Free-First Zero-Downtime Fallback Architecture
- **Status:** Accepted
- **Context:** Production environments may experience external AI API failures, quota exhaustion, or cold starts.
- **Decision:** Wrap recommendation, moderation, and semantic search interfaces in resilient fallback wrappers (`ResilientRecommendationService`, `ResilientModerationService`, `FaultTolerantSearchService`) that seamlessly revert to deterministic heuristics without service disruption.

---

### ADR 008: Next.js 14 App Router & Turborepo Monorepo
- **Status:** Accepted
- **Context:** Shared data types between the backend API and frontend client are critical to avoid schema drift.
- **Decision:** Organize the codebase into a `pnpm` workspace with Turbo: `apps/web` (Next.js 14), `apps/api` (FastAPI), `packages/contracts` (TypeScript schemas), and `packages/ui` (reusable components).
