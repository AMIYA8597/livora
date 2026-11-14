# PHASE 24.7 — Hosted Database Rollback & Recovery Plan

**Document Version:** 1.0  
**Phase:** 24.5 / 24.7 — Reversibility, Schema Downgrade & Recovery Specification  
**Date:** November 15, 2026  
**Auditor Roles:** Principal Database Administrator, Site Reliability Engineer, Disaster Recovery Lead  
**Classification:** Operational Recovery & Rollback Runbook  
**Project:** Flatmate Compatibility & Rental Marketplace  
**Target Project:** `qjwitdovbsfviaepjcul.supabase.co`  

---

## 1. Executive Summary

This document specifies the exact rollback procedures, contingency steps, and recovery options in the event that the hosted database schema migration encounters unexpected behavior, network interruption, or application incompatibility during Phase 24 execution.

---

## 2. Inherent Transactional Rollback (Zero Manual Intervention)

Because the primary migration script `database/migrations/complete_hosted_schema.sql` is executed within an atomic PostgreSQL transaction:
```sql
BEGIN;
... [All DDL and Metadata Statements] ...
COMMIT;
```
If **any single statement** fails during execution:
1. The PostgreSQL engine immediately triggers an automatic `ROLLBACK`.
2. All tables, types, constraints, and indexes created earlier in the script are reverted.
3. The database remains in its clean, pre-migration state.
4. No orphan tables or broken schema fragments can persist.

---

## 3. Explicit Manual Rollback Procedures

If the migration succeeds but subsequent integration testing reveals a critical defect requiring full reversibility:

### 3.1 Scenario A: Complete Schema Reversion (Drop Created Tables)
In the event that the public schema must be returned to its pristine empty state, the following rollback script is prepared:

```sql
BEGIN;

-- Drop RLS Policies
DROP POLICY IF EXISTS "Public profiles are viewable by everyone" ON profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON profiles;
DROP POLICY IF EXISTS "Active properties viewable by everyone" ON properties;
DROP POLICY IF EXISTS "Owners manage own properties" ON properties;
DROP POLICY IF EXISTS "Applicants view own applications" ON rental_applications;
DROP POLICY IF EXISTS "Owners view received applications" ON rental_applications;
DROP POLICY IF EXISTS "Participants view own conversations" ON conversations;
DROP POLICY IF EXISTS "Participants view conversation messages" ON messages;
DROP POLICY IF EXISTS "Users view own notifications" ON notifications;

-- Drop Tables in Reverse Dependency Order
DROP TABLE IF EXISTS outbox_events CASCADE;
DROP TABLE IF EXISTS message_read_receipts CASCADE;
DROP TABLE IF EXISTS message_attachments CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS conversation_preferences CASCADE;
DROP TABLE IF EXISTS conversation_participants CASCADE;
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS safety_check_ins CASCADE;
DROP TABLE IF EXISTS user_blocks CASCADE;
DROP TABLE IF EXISTS moderation_reports CASCADE;
DROP TABLE IF EXISTS verification_documents CASCADE;
DROP TABLE IF EXISTS id_verifications CASCADE;
DROP TABLE IF EXISTS group_wishlist_votes CASCADE;
DROP TABLE IF EXISTS group_wishlist_items CASCADE;
DROP TABLE IF EXISTS group_members CASCADE;
DROP TABLE IF EXISTS groups CASCADE;
DROP TABLE IF EXISTS viewing_appointments CASCADE;
DROP TABLE IF EXISTS rental_applications CASCADE;
DROP TABLE IF EXISTS pg_rules CASCADE;
DROP TABLE IF EXISTS pg_floors CASCADE;
DROP TABLE IF EXISTS pg_buildings CASCADE;
DROP TABLE IF EXISTS flatmate_preferences CASCADE;
DROP TABLE IF EXISTS tenant_memberships CASCADE;
DROP TABLE IF EXISTS roommate_applications CASCADE;
DROP TABLE IF EXISTS roommate_vacancies CASCADE;
DROP TABLE IF EXISTS saved_properties CASCADE;
DROP TABLE IF EXISTS property_amenities CASCADE;
DROP TABLE IF EXISTS beds CASCADE;
DROP TABLE IF EXISTS rooms CASCADE;
DROP TABLE IF EXISTS property_photos CASCADE;
DROP TABLE IF EXISTS properties CASCADE;
DROP TABLE IF EXISTS user_interactions CASCADE;
DROP TABLE IF EXISTS dealbreakers CASCADE;
DROP TABLE IF EXISTS lifestyle_responses CASCADE;
DROP TABLE IF EXISTS user_privacy_settings CASCADE;
DROP TABLE IF EXISTS profiles CASCADE;
DROP TABLE IF EXISTS educational_institutions CASCADE;
DROP TABLE IF EXISTS professional_domains CASCADE;
DROP TABLE IF EXISTS locality_master CASCADE;
DROP TABLE IF EXISTS amenity_catalog CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS alembic_version CASCADE;

COMMIT;
```

### 3.2 Scenario B: Downgrade from Revision `002` to `001` via Alembic
If only the Phase 20A real-time messaging tables need to be rolled back while preserving core user and property tables:
```bash
cd apps/api
python -m alembic downgrade 001_initial_complete_schema
```
Or execute the downgrade migration logic in `apps/api/migrations/versions/002_messaging_realtime_system.py`:
- Drops messaging, attachments, read receipts, conversations, and outbox tables.
- Resets `alembic_version` to `'001_initial_schema'`.

---

## 4. Supabase Point-in-Time Recovery & Backup Strategy

1. **Supabase Native Backups:**
   - Hosted Supabase automatically takes daily physical WAL-level backups.
   - For Pro/Enterprise tiers, Point-in-Time Recovery (PITR) is accessible directly via the Supabase dashboard (`https://supabase.com/dashboard/project/qjwitdovbsfviaepjcul/settings/database`).
2. **Logical Schema Dump Before/After Migration:**
   - Schema snapshots can be retrieved via the Supabase REST/PostgREST OpenAPI definitions or pg_dump from a CI runner.

---

## 5. Rollback Verification

Following any rollback execution:
1. Verify `GET /rest/v1/alembic_version` state.
2. Verify table count in `public` schema via `GET /rest/v1/`.
3. Confirm API health endpoints return expected codes.
