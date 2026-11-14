# PHASE 23.5 — Hosted Migration Execution and Rollback Plan

**Document Version:** 1.0  
**Phase:** 23.5 — Hosted Migration Execution & Governance  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Database Administrator, Release Engineer, DevSecOps Architect  
**Classification:** Migration Execution, Rollback & Disaster Recovery Runbook  
**Target Project:** `https://qjwitdovbsfviaepjcul.supabase.co` (`qjwitdovbsfviaepjcul`)  
**Target Environment:** Staging / Production Candidate  

---

## 1. Executive Summary

This document establishes the migration execution protocol, destructive statement review, backup requirements, rollback plans, and approval gates for applying database schema changes to the hosted Supabase PostgreSQL project.

In strict accordance with **Rule 0**:
> **Explicit approval is required before:**
> - Applying hosted schema migrations.
> - Modifying production data.
> - Destructive database operations.

---

## 2. Pre-Migration Verification & Approval Gate

| Checklist Item | Requirement | Verification Status | Evidence / Notes |
| :--- | :--- | :---: | :--- |
| **Target Project** | `qjwitdovbsfviaepjcul.supabase.co` | **CONFIRMED** | Project ref `qjwitdovbsfviaepjcul` (ap-south-1) |
| **Target Environment** | Staging / Pre-Production | **CONFIRMED** | Environment: Staging |
| **Backup Verification** | Verified automated or point-in-time backup | **REQUIRED PRIOR TO APPLY** | Supabase automated snapshot or `pg_dump` |
| **Destructive SQL Scan** | Zero `DROP`, `TRUNCATE`, or destructive alters | **PASSED** | Reviewed in Phase 23.4 (Zero destructive statements) |
| **Transaction Wrapping** | Atomic execution (`BEGIN` ... `COMMIT`) | **PASSED** | Wrapped in transaction block |
| **Rollback Script** | Tested reverse migration SQL | **PREPARED** | Downgrade scripts documented below |
| **Explicit User Approval** | Human architect authorization | **AWAITING USER APPROVAL** | Held at approval boundary |

---

## 3. Migration SQL Review & Safety Assessment

The reviewed migration artifact `database/migrations/complete_hosted_schema.sql`:
- **Statement Count:** 43 table creations, 62 index creations, 1 metadata update.
- **Destructive Statements:** **0**
- **Idempotency:** All statements use `IF NOT EXISTS` guards.
- **Data Integrity:** Table creation preserves existing data if tables already exist.
- **Alembic Alignment:** Final statement sets `alembic_version` to `'002_messaging_realtime'`.

---

## 4. Rollback and Disaster Recovery Procedures

### 4.1 Forward-Recovery (Preferred)
In case of a partial failure during migration:
1. Because the entire script runs inside a transaction block (`BEGIN; ... COMMIT;`), PostgreSQL rolls back all partial changes automatically upon encountering any syntax or permission error.
2. The database state remains completely clean at the previous state.

### 4.2 Explicit Rollback (Downgrade)
If migration needs to be reversed after successful execution:
```sql
BEGIN;
-- Reverse 002_messaging_realtime:
DROP TABLE IF EXISTS outbox_events CASCADE;
DROP TABLE IF EXISTS conversation_preferences CASCADE;
DROP TABLE IF EXISTS conversation_read_cursors CASCADE;
DROP TABLE IF EXISTS attachments CASCADE;
ALTER TABLE messages DROP COLUMN IF EXISTS is_deleted;
ALTER TABLE messages DROP COLUMN IF EXISTS deleted_at;
ALTER TABLE messages DROP COLUMN IF EXISTS reply_to_message_id;
ALTER TABLE conversations DROP COLUMN IF EXISTS flatmate_match_id;
ALTER TABLE conversations DROP COLUMN IF EXISTS group_id;
ALTER TABLE conversations DROP COLUMN IF EXISTS application_id;
UPDATE alembic_version SET version_num = '001_initial_schema';
COMMIT;
```

---

## 5. Execution Methods

Due to perimeter firewall egress filtering on ports 5432 and 6543 from the local Windows machine, the migration can be executed via two approved paths:

### Method A: Automated GitHub Actions CI/CD Runner (Recommended)
Workflow `.github/workflows/hosted-db-migration.yml` runs on GitHub-hosted cloud runners with unrestricted outbound access to Supabase poolers:
```yaml
name: Hosted DB Migration
on:
  workflow_dispatch:
    inputs:
      target_env:
        description: 'Environment (staging/production)'
        required: true
        default: 'staging'
```
The runner runs `alembic upgrade head` over the secure pooler connection using GitHub repository secrets.

### Method B: Supabase Dashboard SQL Editor
The reviewed file `database/migrations/complete_hosted_schema.sql` can be pasted directly into the Supabase Dashboard SQL Editor (`https://supabase.com/dashboard/project/qjwitdovbsfviaepjcul/sql`) and executed with one click.

---

## 6. Approval Boundary Sign-Off

**Status:** HELD AT APPROVAL BOUNDARY.  
No migrations will be executed against the hosted database without explicit user confirmation.
