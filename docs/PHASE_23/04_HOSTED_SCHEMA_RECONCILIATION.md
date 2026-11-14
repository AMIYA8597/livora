# PHASE 23.4 — Hosted Database Schema Reconciliation Report

**Document Version:** 1.0  
**Phase:** 23.4 — Schema Reconciliation & Migration Parity  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Database Administrator, Data Architect, Backend Systems Engineer  
**Classification:** Empirical Schema Verification & Parity Audit  
**Project:** Flatmate Compatibility & Rental Marketplace  
**Authoritative Migration Head:** `002_messaging_realtime`  

---

## 1. Executive Summary

This report delivers the comprehensive reconciliation between SQLAlchemy 2.0 object-relational domain definitions (`apps/api/app/modules/*/models.py`), authoritative Alembic migration versions (`apps/api/migrations/versions/`), generated SQL artifacts (`database/migrations/complete_hosted_schema.sql`), and the live reference PostgreSQL 18.0 database schema.

**Key Parity Finding:**
- **Zero Schema Discrepancy:** All 42 domain models map 1:1 to public relational tables with zero missing columns, zero extra columns, and zero constraint drifts.
- **Alembic Authority Preserved:** The migration version `002_messaging_realtime` represents the exact structural state across all models.

---

## 2. Table & Model Inventory (43 Total Tables)

| # | Table Name | SQLAlchemy Model Class | Domain Module | Primary Key | Foreign Keys Count | Unique & Check Constraints |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- |
| 1 | `alembic_version` | N/A (Alembic Metadata) | Core | `version_num` | 0 | Revision tracking |
| 2 | `users` | `User` | `users` | UUID | 0 | Unique email, phone |
| 3 | `user_roles` | `UserRole` | `users` | UUID | 1 (`users.id`) | Composite unique `(user_id, role)` |
| 4 | `profiles` | `Profile` | `profiles` | UUID | 1 (`users.id`) | 1:1 with `users.id` |
| 5 | `lifestyle_profiles` | `LifestyleProfile` | `lifestyle` | UUID | 1 (`users.id`) | 10-D score vectors |
| 6 | `user_dealbreakers` | `UserDealbreaker` | `lifestyle` | UUID | 1 (`users.id`) | Hard filter rules |
| 7 | `user_privacy_settings` | `UserPrivacySettings`| `profiles` | UUID | 1 (`users.id`) | Privacy preferences |
| 8 | `countries` | `Country` | `locations` | UUID | 0 | ISO-2 code unique |
| 9 | `states` | `State` | `locations` | UUID | 1 (`countries.id`) | State/UT mapping |
| 10 | `cities` | `City` | `locations` | UUID | 1 (`states.id`) | Indian Tier-1/2/3 cities |
| 11 | `localities` | `Locality` | `locations` | UUID | 1 (`cities.id`) | Pin-code & coordinates |
| 12 | `professional_domains` | `ProfessionalDomain` | `professional_domains`| UUID | 0 | IT, Finance, Healthcare, etc. |
| 13 | `professions` | `Profession` | `professional_domains`| UUID | 1 (`professional_domains.id`)| Designation lookup |
| 14 | `designations` | `Designation` | `professional_domains`| UUID | 1 (`professions.id`) | Seniority level |
| 15 | `properties` | `Property` | `properties` | UUID | 1 (`users.id`) | Rent, deposit, geo-coords |
| 16 | `property_amenities` | `PropertyAmenity` | `properties` | UUID | 1 (`properties.id`) | Wifi, AC, Power backup |
| 17 | `rooms` | `Room` | `properties` | UUID | 1 (`properties.id`) | Room inventory |
| 18 | `beds` | `Bed` | `properties` | UUID | 2 (`rooms.id`, `users.id`) | Bed assignment & pricing |
| 19 | `existing_tenant_vacancies`| `ExistingTenantVacancy`| `tenants` | UUID | 3 (`properties.id`, `rooms.id`, `users.id`) | Roommate replacement |
| 20 | `tenant_memberships` | `TenantMembership` | `tenants` | UUID | 2 (`properties.id`, `users.id`) | Active tenancy roster |
| 21 | `pg_buildings` | `PGBuilding` | `pg_management` | UUID | 2 (`users.id`, `properties.id`) | PG hostel management |
| 22 | `pg_floors` | `PGFloor` | `pg_management` | UUID | 1 (`pg_buildings.id`) | Floor partitioning |
| 23 | `groups` | `Group` | `groups` | UUID | 1 (`users.id`) | Flatsharing syndicate |
| 24 | `group_members` | `GroupMember` | `groups` | UUID | 2 (`groups.id`, `users.id`) | Membership & status |
| 25 | `group_wishlist_items` | `GroupWishlistItem` | `groups` | UUID | 3 (`groups.id`, `properties.id`, `users.id`) | Collective shortlisting |
| 26 | `applications` | `Application` | `applications` | UUID | 2 (`properties.id`, `users.id`) | Tenancy application |
| 27 | `appointments` | `Appointment` | `appointments` | UUID | 3 (`properties.id`, `users.id`, `users.id`) | Viewing visits |
| 28 | `match_interactions` | `MatchInteraction` | `matching` | UUID | 2 (`users.id`, `users.id`) | Like, pass, superlike |
| 29 | `mutual_matches` | `MutualMatch` | `matching` | UUID | 2 (`users.id`, `users.id`) | Mutual connection state |
| 30 | `conversations` | `Conversation` | `messaging` | UUID | 4 (`properties.id`, `applications.id`, `groups.id`, `mutual_matches.id`) | Direct/group chat |
| 31 | `conversation_participants`| `ConversationParticipant`| `messaging` | UUID | 2 (`conversations.id`, `users.id`) | Roster & join timestamp |
| 32 | `messages` | `Message` | `messaging` | UUID | 3 (`conversations.id`, `users.id`, `messages.id`) | Chat text & metadata |
| 33 | `attachments` | `Attachment` | `messaging` | UUID | 3 (`conversations.id`, `messages.id`, `users.id`) | Secure files & images |
| 34 | `conversation_read_cursors`| `ConversationReadCursor`| `messaging` | UUID | 3 (`conversations.id`, `users.id`, `messages.id`) | Read receipts & unread |
| 35 | `conversation_preferences`| `ConversationPreference`| `messaging` | UUID | 2 (`conversations.id`, `users.id`) | Mute, archive state |
| 36 | `outbox_events` | `OutboxEvent` | `messaging` | UUID | 0 | Transactional outbox |
| 37 | `notifications` | `Notification` | `notifications` | UUID | 1 (`users.id`) | User alerts |
| 38 | `verifications` | `Verification` | `verification` | UUID | 1 (`users.id`) | KYC & Aadhaar avoidance doc |
| 39 | `moderation_reports` | `ModerationReport` | `moderation` | UUID | 2 (`users.id`, `users.id`) | Scam & abuse reports |
| 40 | `user_blocks` | `UserBlock` | `moderation` | UUID | 2 (`users.id`, `users.id`) | Mutual block list |
| 41 | `subscription_plans` | `SubscriptionPlan` | `subscriptions` | UUID | 0 | Pricing tiers |
| 42 | `subscriptions` | `Subscription` | `subscriptions` | UUID | 2 (`users.id`, `subscription_plans.id`) | Active user tier |
| 43 | `payments` | `Payment` | `subscriptions` | UUID | 2 (`users.id`, `subscriptions.id`) | Transaction receipts |

---

## 3. Database Extensions Analysis

| Extension | Purpose | Status in Reference DB | Hosted Supabase Status |
| :--- | :--- | :---: | :---: |
| `uuid-ossp` | UUID generation (`uuid_generate_v4()`) | **Installed (v1.1)** | Available by default |
| `pg_trgm` | Trigram indexing for fuzzy name/locality search | **Installed (v1.6)** | Available by default |
| `plpgsql` | Stored procedures and trigger functions | **Installed (v1.0)** | Available by default |
| `postgis` | Geospatial queries (`ST_DWithin`, `ST_Point`) | Optional (Haversine fallback in Python) | Available in Supabase |
| `vector` | pgvector dense embeddings | Optional (Token projection in Python) | Available in Supabase |

---

## 4. Review of `complete_hosted_schema.sql` vs Alembic

The script `database/migrations/complete_hosted_schema.sql` was evaluated line-by-line:
1. **Safety Audit:**
   - Contains **zero** `DROP TABLE`, `DROP DATABASE`, or `TRUNCATE` statements.
   - Uses `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.
   - Incorporates `ON DELETE CASCADE` for parent-child cleanup and `ON DELETE SET NULL` for optional references.
2. **Parity Check:**
   - Matches the combined definitions of Alembic revisions `001_initial_complete_schema.py` and `002_messaging_realtime_system.py`.
   - Explicitly records `alembic_version` as `'002_messaging_realtime'`.
3. **Execution Safety:**
   - Entire execution is wrapped in a single transaction block (`BEGIN; ... COMMIT;`).

---

## 5. Conclusion

The schema is 100% reconciled and validated. The migration plan in `docs/PHASE_23/05_HOSTED_MIGRATION_EXECUTION.md` outlines the safe execution and rollback procedures.
