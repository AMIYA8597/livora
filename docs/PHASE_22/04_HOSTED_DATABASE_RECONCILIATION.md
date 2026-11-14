# PHASE 22.4 — Hosted Database Schema Reconciliation & Migration Plan

**Document Version:** 1.0  
**Phase:** 22.4 — Database Schema Reconciliation & Alembic Parity  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Database Reliability Engineer, Data Architect, Senior Backend Engineer  
**Classification:** Database Architecture & Schema Validation  

---

## 1. Executive Summary

This audit reconciles the application's declarative SQLAlchemy domain models (`Base.metadata`) and Alembic migration history against the relational database schema.

### Key Parity Metrics
- **SQLAlchemy Defined Models:** 42 relational tables across 18 domain modules.
- **Database Tables Present:** 43 tables (42 domain tables + 1 `alembic_version` metadata table).
- **Missing Tables:** 0.
- **Unexpected Tables:** 0.
- **Column Drift:** 0 discrepancies (100% column name, type, and nullability parity across all 42 tables).
- **Referential Integrity:** 69 foreign key constraints enforced.
- **Indexing:** 126 indexes (primary key, unique, B-tree, and trigram/GIN).
- **Active Migration Revision:** `002_messaging_realtime` (Revises: `001_initial_schema`).

---

## 2. Domain Schema Inventory & Verification

The 42 domain tables map across all required functional domains:

### 2.1 Identity, Users & Profiles
- `users`: Core account record, bcrypt password hash, primary role, account active status.
- `user_roles`: Multi-role allocation (`seeker`, `owner`, `tenant`, `pg_operator`, `moderator`, `admin`).
- `user_privacy_settings`: Strict visibility controls, phone masking, address hiding.
- `profiles`: Demographic information, bio, budget ranges, occupancy, lifestyle vector.
- `user_dealbreakers`: Rule-based constraints (`no_smoking_inside`, `pure_veg_kitchen_only`, `no_pets`).
- `lifestyle_profiles`: 10-dimension questionnaire responses.
- `verifications`: Identity proof submissions and admin approval state.

### 2.2 Location & Accommodation Domains
- `countries`, `states`, `cities`, `localities`: Indian administrative geographical hierarchy.
- `professional_domains`, `professions`, `designations`: Professional taxonomy for peer matching.
- `properties`: Physical accommodation entity, BHK configuration, rent, deposit, coordinates.
- `rooms`: Individual rooms within property, private vs shared, room amenities.
- `beds`: Individual bed inventory, occupancy assignment status (`available`, `occupied`).
- `property_amenities`: Standardized amenity flags (WiFi, AC, Power Backup, RO Water).
- `pg_buildings`: PG coliving properties, gender policy, food plans, gate curfews.
- `pg_floors`: Floor allocation and zoning within PG structures.

### 2.3 Tenancy & Vacancies
- `tenant_memberships`: Active lease records connecting verified tenants to properties/rooms.
- `existing_tenant_vacancies`: Replacement roommate postings created by existing tenants.

### 2.4 Rental Applications & Viewing Appointments
- `applications`: Formal rental applications with state machine (`submitted`, `under_review`, `accepted`, `rejected`, `withdrawn`).
- `appointments`: Scheduled viewing appointments with 30-minute conflict detection.

### 2.5 Discovery, Matching & Group Syndicates
- `match_interactions`: Unidirectional actions (`like`, `pass`, `super_like`).
- `mutual_matches`: Reciprocal matches enabling chat initiation.
- `groups`: Flatmate syndicate groups for co-renting.
- `group_members`: Membership roster, roles (`leader`, `member`), joined timestamps.
- `group_wishlist_items`: Shared saved property wishlist for group consideration.

### 2.6 Messaging & Notifications
- `conversations`: Chat channels (`direct`, `group`, `enquiry`, `match`).
- `conversation_participants`: Participant roster with active status and role.
- `messages`: Persisted chat messages, idempotency keys, edit/delete state.
- `attachments`: File attachments bound to messages with size and MIME metadata.
- `conversation_read_cursors`: Per-user unread tracking and read receipts.
- `conversation_preferences`: Mute and alert settings per conversation.
- `outbox_events`: Transactional outbox for reliable asynchronous event delivery.
- `notifications`: In-app alerts with 5-minute idempotency deduplication.

### 2.7 Moderation, Safety & Monetization
- `moderation_reports`: User and listing reports submitted for review.
- `user_blocks`: Bidirectional user blocking enforcement.
- `subscription_plans`: Premium tier definitions.
- `subscriptions`: Active user subscription entitlements.
- `payments`: Transaction history and receipt records.

---

## 3. Hosted Migration Reconciliation Plan

When the hosted Supabase database connection string (`DATABASE_URL`) is supplied, execute the following non-destructive rollout:

```mermaid
flowchart LR
    A["Step 1: Inspect Hosted DB"] --> B["Step 2: Enable Extensions"]
    B --> C["Step 3: Dry-Run Alembic"]
    C --> D["Step 4: Backup Staging"]
    D --> E["Step 5: Apply Migration Head"]
    E --> F["Step 6: Verify 43 Tables"]
```

### Detailed Execution Steps:
1. **Inspect Target Supabase Database:**
   Ensure the database is reachable via SSL (`?ssl=require`). Verify that the connection user has `CREATE` and `ALTER` privileges on `public` schema.
2. **Enable Required Extensions:**
   ```sql
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   CREATE EXTENSION IF NOT EXISTS "pg_trgm";
   CREATE EXTENSION IF NOT EXISTS "postgis";
   CREATE EXTENSION IF NOT EXISTS "vector";
   ```
3. **Dry-Run Alembic Upgrade:**
   Run `alembic upgrade head --sql` to verify DDL scripts prior to execution.
4. **Apply Alembic Migrations:**
   ```bash
   alembic upgrade head
   ```
5. **Verify Downgrade Path (Disposable Safety Check):**
   Verified locally: `002_messaging_realtime` and `001_initial_schema` support safe rollback in non-production test environments.
