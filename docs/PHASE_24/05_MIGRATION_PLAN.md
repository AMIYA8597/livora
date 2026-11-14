# PHASE 24.5 — Hosted PostgreSQL Migration Plan & Approval Specification

**Document Version:** 1.0  
**Phase:** 24.5 — Migration Review, Execution Strategy & Preflight Gate  
**Date:** November 15, 2026  
**Auditor Roles:** Principal Database Reliability Engineer, Infrastructure Architect, Lead Release Engineer  
**Classification:** Authoritative Migration Specification & Approval Gate  
**Target Project:** `https://qjwitdovbsfviaepjcul.supabase.co` (`qjwitdovbsfviaepjcul`)  
**Target Environment:** Staging / Hosted Supabase (AWS Mumbai `ap-south-1`)  
**Target Alembic Head:** `002_messaging_realtime`  

---

## 1. Executive Summary & Purpose

This document outlines the exact, repeatable, and non-destructive migration execution plan for deploying the complete Flatmate data tier onto the hosted Supabase PostgreSQL infrastructure.

In strict accordance with **Non-Negotiable Rules**:
- **Alembic Authority:** Alembic remains the sole schema version authority.
- **Atomic Transactionality:** The migration executes inside a single `BEGIN ... COMMIT` block.
- **Pre-validated on Disposable Database:** The migration package was tested and verified on a clean disposable PostgreSQL instance, confirming that all 43 tables, 58 foreign keys, 92 indexes, and 33 RLS policies apply cleanly without errors.
- **Defect Remediated:** A UTF-8 Byte Order Mark (BOM) in `complete_hosted_schema.sql` that would have caused parser syntax errors was identified during preflight testing and eliminated.

---

## 2. Target Schema Objects & Affected Scope

The migration package applies the following objects in topological order:

| Domain | Table Names | Count | Indexes & Constraints |
| :--- | :--- | :---: | :--- |
| **System & Migration Tracking** | `alembic_version` | 1 | Primary Key: `version_num` |
| **Identity & Access** | `users`, `profiles`, `user_privacy_settings` | 3 | Unique index on email, phone index, FK to users |
| **Lifestyle & Matching** | `lifestyle_responses`, `dealbreakers`, `user_interactions` | 3 | Composite unique constraint, FKs to users |
| **Properties & Inventory** | `properties`, `property_photos`, `rooms`, `beds`, `property_amenities`, `saved_properties` | 6 | Spatial/trigram indexes, cascade deletion, unique beds |
| **Tenancy & Roommates** | `roommate_vacancies`, `roommate_applications`, `tenant_memberships`, `flatmate_preferences` | 4 | Status indexes, unique active vacancies |
| **PG Management** | `pg_buildings`, `pg_floors`, `pg_rules` | 3 | Building hierarchy, unique floor numbers |
| **Applications & Bookings** | `rental_applications`, `viewing_appointments` | 2 | Unique active applications, slot indexes |
| **Group Syndicates** | `groups`, `group_members`, `group_wishlist_items`, `group_wishlist_votes` | 4 | Unique member associations, group voting rules |
| **Trust & Moderation** | `id_verifications`, `verification_documents`, `moderation_reports`, `user_blocks`, `safety_check_ins` | 5 | Unique blocks, document verification states |
| **Realtime Messaging** | `conversations`, `conversation_participants`, `conversation_preferences`, `messages`, `message_attachments`, `message_read_receipts`, `notifications`, `outbox_events` | 8 | Sequence numbers, read cursors, outbox status index |
| **Reference Taxonomies** | `professional_domains`, `educational_institutions`, `amenity_catalog`, `locality_master` | 4 | Master taxonomies and geographical metadata |

**Total Objects Created:** 43 tables, 58 foreign keys, 92 indexes, 33 RLS policies.

---

## 3. Migration Package Artifacts

1. **`database/migrations/complete_hosted_schema.sql`:**
   - 1,048 lines of pure ANSI/PostgreSQL DDL.
   - Enclosed in `BEGIN; ... COMMIT;`.
   - Idempotent extension creation (`uuid-ossp`, `pg_trgm`).
   - Clean UTF-8 encoding (BOM stripped).
   - Sets `alembic_version` to `'002_messaging_realtime'`.
2. **`database/policies/rls_policies.sql`:**
   - Enables RLS on all 12 sensitive user/application/messaging tables.
   - Creates 33 granular security policies for non-superuser roles.
3. **`.github/workflows/hosted-db-migration.yml`:**
   - CI/CD automation runner executing `alembic upgrade head` over standard outbound port 5432.

---

## 4. Execution Channels & Procedures

### Execution Channel A: Supabase Dashboard SQL Editor (Primary / Instant)
Because the local workstation cannot open outbound TCP port 5432 due to ISP firewall rules, execution via Supabase SQL Editor runs directly inside Supabase's hosted control plane:
1. Navigate to: `https://supabase.com/dashboard/project/qjwitdovbsfviaepjcul/sql`
2. Open `database/migrations/complete_hosted_schema.sql` and click **Run**.
3. Open `database/policies/rls_policies.sql` and click **Run**.
4. Expected execution time: ~1.2 seconds.

### Execution Channel B: GitHub Actions Migration Pipeline (Automated / Headless)
If running via CI/CD:
1. Ensure GitHub Actions repository secret `STAGING_DATABASE_URL` is set to the session pooler connection string:
   `postgresql://postgres.qjwitdovbsfviaepjcul:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require`
2. Trigger `.github/workflows/hosted-db-migration.yml`:
   - Target environment: `staging`
   - Action: `upgrade_head`
   - Confirmation: `APPLY_MIGRATION`
3. Runner executes `alembic upgrade head`, logs are masked and audited.

---

## 5. Post-Migration Verification Checklist

Upon execution, the following verification commands will be run:
1. Interrogate PostgREST schema: Verify 42 public domain tables appear in `/rest/v1/`.
2. Interrogate `alembic_version`: Confirm `GET /rest/v1/alembic_version` returns `[{ "version_num": "002_messaging_realtime" }]`.
3. Interrogate RLS: Verify policies on `users`, `properties`, `applications`, `conversations`, `messages`, `notifications`.
4. Run live backend and frontend tests against the updated hosted schema.

---

## 6. Official Approval Request Notice

> [!IMPORTANT]
> **MIGRATION APPROVAL GATE (STAGE 24.5)**  
> Execution of the schema migration against hosted project `qjwitdovbsfviaepjcul` requires explicit project owner review and authorization.  
> Details:
> - **SQL File:** `database/migrations/complete_hosted_schema.sql` (and `database/policies/rls_policies.sql`)
> - **Affected Objects:** 43 new tables, 58 foreign keys, 92 indexes, 33 RLS policies in `public` schema.
> - **Destructive Operations:** None. Zero existing tables or data are dropped, truncated, or overwritten (hosted public schema is currently empty).
> - **Rollback Plan:** `docs/PHASE_24/07_ROLLBACK_PLAN.md`
