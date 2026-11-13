# Phase 20 Database Deployment & Migration Architecture

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** PostgreSQL Database Administrator  

---

## 1. PostgreSQL Architecture & Extensions

The staging database runs on PostgreSQL 15 managed by Supabase in the Mumbai (`ap-south-1`) region.

### Mandatory PostgreSQL Extensions
The following extensions are enabled and validated in staging:
1. `postgis` (v3.3+): Provides spatial types (`geography(Point, 4326)`), spherical distance computations (`ST_DWithin`, `ST_Distance`), and spatial GiST indexing on property coordinates.
2. `vector` / `pgvector` (v0.5+): Provides high-dimensional vector embeddings and indexing (`vector(64)` with Cosine distance indexing `vector_cosine_ops`) for the 10-dimension flatmate compatibility engine.
3. `uuid-ossp` / `pgcrypto`: Generates cryptographically secure RFC 4122 UUID v4 primary keys.

---

## 2. Schema Migration & Source of Truth

**Single Source of Truth:** Alembic is the canonical schema migration manager. Direct SQL schema drifts are prohibited.

### Migration History & Revisions
1. `001_initial_schema`:
   - Users, User Roles (`seeker`, `owner`, `tenant`, `pg_operator`, `admin`).
   - Profiles, Professional Details, Lifestyle Survey & Vectors (`vector(64)`).
   - Dealbreaker Rules, Mutual Matches, Pairwise Interactions.
   - Properties (`geography(Point, 4326)`), Rooms, Beds, Amenities, Media Attachments.
   - Rental Applications, Viewing Appointments.
   - Existing Tenant Memberships, Tenant Vacancies.
   - PG Buildings, PG Floors, Room Capacities.
   - Flatmate Groups, Memberships, Wishlist Voting Items.
   - Moderation Reports, User Blocks, Verification Documents.
2. `002_messaging_realtime`:
   - Conversations (`direct`, `group`), Conversation Participants (`is_muted`, `last_read_message_id`).
   - Messages (`idempotency_key`, `content`, `message_type`, `attachments`, `deleted_at`).
   - Read Cursors, Ephemeral Typing Events, Optimistic Delivery Status tracking.

---

## 3. Connection Pooling Architecture

To prevent connection exhaustion under asynchronous FastAPI concurrency, dual connection URIs are configured:
- **Transaction Pooler (Supavisor on Port 6543):**
  - Assigned to `DATABASE_URL` for FastAPI runtime async sessions.
  - Efficiently multiplexes 500+ client connections into a compact pool of 15 backend PostgreSQL connections.
  - Statement caching disabled (`statement_cache_size=0`) to support transaction pooling safely.
- **Direct Session Connection (Port 5432):**
  - Assigned to `DIRECT_URL` for Alembic schema migrations and DDL operations.
  - Ensures schema alterations, index creations, and locks execute on dedicated database sessions.

---

## 4. Staging Seed Verification

The database staging environment is seeded using the idempotent script [`database/seeds/staging_seed.py`](file:///D:/work/flatmate/database/seeds/staging_seed.py).
- **Synthetic Personas:** Seeker students, young professionals, property owners, PG operators, existing tenants, and compliance moderators.
- **Geographic Coverage:** Real Bangalore coordinates (Indiranagar, Koramangala, HSR Layout, Whitefield, Electronic City) with valid PostGIS points.
- **Vector Embeddings:** Valid 64-dimensional synthetic lifestyle embeddings for compatibility matching.
- **Property Inventory:** Multi-room apartments, individual bed listings, coed and female-only PG floors.
- **Zero Production Data:** All emails end in `@synth.flatmate.test` with synthetic phone numbers conforming to E.164 formats (+91 98765 00001–00008).
