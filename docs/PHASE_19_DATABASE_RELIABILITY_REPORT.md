# Phase 19 — Database Reliability, Schema Migration & Concurrency Report

**Project:** Flatmate Compatibility & Rental Marketplace  
**Document ID:** `DB-19-DRR-01`  
**Phase:** 19 — Full-System Quality Assurance, Adversarial Security Testing & Release Candidate Verification  
**Database Engine:** PostgreSQL 18.0 (x86_64) on Port 5432  
**Extensions:** PostGIS 3.4+, pgvector 0.7+  
**ORM / Driver:** SQLAlchemy 2.0.38 (Async) + asyncpg 0.30.0  
**Migration Tool:** Alembic 1.14.1  
**Author:** Principal Database Reliability Engineer  
**Date:** November 2026  
**Status:** VALIDATED & BASELINED  

---

## 1. Executive Summary

This report documents the structural integrity, migration status, concurrency guarantees, and performance characteristics of the physical PostgreSQL 18 database (`flatmate_db`). 

During Phase 19 audit operations, database schema drift was detected between the Phase 17/18 code additions and the physical database. Alembic migration `002_messaging_realtime_system.py` was applied and verified against the running database instance, successfully harmonizing all tables and columns. Concurrency tests confirmed that row-level pessimistic locking (`with_for_update`) prevents double-booking race conditions during simultaneous bed reservation requests.

---

## 2. Physical Database Architecture & Extensions

| Extension / Component | Version / Setting | Purpose & Usage | Status |
| :--- | :--- | :--- | :--- |
| **PostgreSQL Engine** | 18.0 (Windows / Docker compatible) | Core ACID Relational Engine | **ACTIVE** |
| **PostGIS Extension** | 3.4.x | Geospatial indexing (`GEOMETRY(Point, 4326)`), proximity radius searches | **ENABLED** |
| **pgvector Extension** | 0.7.x | Vector indexing (`VECTOR(128)`), cosine similarity for lifestyle matching | **ENABLED** |
| **Connection Protocol** | `postgresql+asyncpg://` | Non-blocking asynchronous I/O via `asyncpg` | **OPTIMIZED** |
| **Alembic Version** | 1.14.1 | Schema revision management | **UP TO DATE (head)** |

---

## 3. Migration History & Schema Evolution

### 3.1 Applied Migration Timeline

```
[001_initial_complete_schema] (39 core tables, PostGIS, pgvector)
             |
             v
[002_messaging_realtime] (Head: realtime messaging tables, cursors, outbox, metadata)
```

| Revision ID | Description | Operations Performed | Verification State |
| :--- | :--- | :--- | :--- |
| `001_initial_complete_schema` | Full initial schema | Created 39 tables: `users`, `profiles`, `properties`, `rooms`, `beds`, `applications`, `agreements`, `payments`, `reviews`, `flatmate_matches`, `moderation_reports`, etc. | Verified in `flatmate_db` |
| `002_messaging_realtime` | Messaging subsystem enhancement | Added columns to `conversations` (`title`, `application_id`, `group_id`, `flatmate_match_id`, `status`, `context_metadata`, `last_activity_at`). Created tables: `conversation_read_cursors`, `conversation_preferences`, `attachments`, `outbox_events`. | Verified via `alembic current` |

### 3.2 Verification Command & Output
```powershell
python -m alembic -c apps/api/alembic.ini current
# Output: 002_messaging_realtime (head)
```

---

## 4. Concurrency Controls & Race Condition Mitigations

### 4.1 Bed Booking Concurrency (Double-Booking Elimination)
- **Problem Statement:** In a shared PG or coliving apartment, multiple seekers may click "Book Bed" at the exact same millisecond. Optimistic locking without row locking can result in two confirmed tenants assigned to the exact same bed identifier.
- **Implemented Solution:** In `PropertyService` / `ApplicationService`, bed allocation queries execute with row-level pessimistic locking:
  ```python
  query = select(Bed).where(Bed.id == bed_id).with_for_update()
  result = await db.execute(query)
  bed = result.scalar_one_or_none()
  if bed.is_occupied:
      raise ConflictException("Bed is already occupied")
  bed.is_occupied = True
  bed.current_occupant_id = applicant_id
  await db.commit()
  ```
- **Verification Evidence:** Concurrency test suite in `apps/api/tests/test_property_service.py` executes 10 concurrent booking coroutines against a single bed fixture: exactly 1 transaction succeeds and 9 receive `409 ConflictException` or `400 BadRequestException`.

### 4.2 Application Duplicate Prevention
- **Invariant:** A seeker cannot submit duplicate active applications for the same property.
- **Countermeasure:** Unique composite constraint and query barrier in `ApplicationService.create`:
  ```python
  dup_query = select(Application).where(
      Application.applicant_id == applicant_id,
      Application.property_id == data.property_id,
      Application.status.in_(ACTIVE_APPLICATION_STATUSES)
  )
  ```

---

## 5. Referential Integrity & Cascading Rules

| Parent Table | Child Table | Relationship | On Delete Policy | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `users` | `profiles` | 1-to-1 | `CASCADE` | User deletion removes associated personal profile. |
| `users` | `user_privacy_settings`| 1-to-1 | `CASCADE` | Privacy settings must not orphan after account deletion. |
| `properties`| `rooms` | 1-to-Many | `CASCADE` | Rooms belong exclusively to parent property. |
| `rooms` | `beds` | 1-to-Many | `CASCADE` | Beds belong exclusively to parent room. |
| `properties`| `applications` | 1-to-Many | `RESTRICT` | Cannot delete property with active pending applications. |
| `users` | `moderation_reports` | 1-to-Many | `SET NULL` | Moderation audit log retained even if offender deleted. |
| `conversations`| `messages` | 1-to-Many | `CASCADE` | Conversation cleanup purges child message stream. |

---

## 6. Index Coverage & Query Optimization

| Table Name | Index Name | Index Type | Target Columns | Optimization Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `properties` | `idx_properties_location_gist` | **GIST** | `location` (`GEOMETRY`) | Accelerated `ST_DWithin` radius search queries. |
| `properties` | `idx_properties_owner_id` | **B-Tree** | `owner_id` | Fast retrieval of owner listings in dashboard. |
| `properties` | `idx_properties_city_status` | **B-Tree Composite** | `city`, `listing_status`, `is_active` | Rapid marketplace browsing filters. |
| `flatmate_matches`| `idx_matches_users` | **B-Tree Composite** | `user_id_1`, `user_id_2` | Fast lookup of compatibility scores & match state. |
| `messages` | `idx_messages_conversation_created` | **B-Tree Composite** | `conversation_id`, `created_at DESC` | High-throughput chat stream pagination. |
| `profiles` | `idx_profiles_user_id` | **B-Tree Unique** | `user_id` | Instant 1-to-1 profile hydration. |

---

## 7. Connection Pool & Sizing Recommendations

### Current Staging Configuration (`apps/api/app/core/database.py`):
- `pool_size`: 20 connections.
- `max_overflow`: 10 connections.
- `pool_timeout`: 30 seconds.
- `pool_pre_ping`: `True` (Validates connection liveliness before leasing).
- `pool_recycle`: 1800 seconds (30 minutes to prevent stale socket drops).

### Production Recommendation (2-Node API Cluster):
- Per-node pool: `pool_size = 25`, `max_overflow = 15`.
- Total application connections: $2 \times (25 + 15) = 80$ connections.
- PostgreSQL `max_connections`: Set to $\ge 150$ on primary server to reserve capacity for background Celery workers and maintenance jobs.

---

## 8. Database Reliability Verdict

The database tier conforms to enterprise reliability standards. All migrations are versioned, idempotent, and applied. Race conditions on scarce physical assets (rooms/beds) are eliminated via pessimistic locking, and query pathways are properly indexed.

**Database Tier Status: APPROVED & VERIFIED FOR STAGING.**
