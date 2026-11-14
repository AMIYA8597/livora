# PHASE 23.4 & 23.5 — Migration Execution and Rollback Strategy Report

**Document Version:** 1.0  
**Phase:** 23.4 / 23.5 — Migration Execution Protocol & Operational Guardrails  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Database Reliability Engineer, Application Security Engineer  
**Classification:** Migration Procedure, Pre-Flight Validation & Rollback Runbook  
**Target Hosted Project:** `qjwitdovbsfviaepjcul` (Supabase AWS Mumbai)  

---

## 1. Executive Summary

This report defines the migration execution plan, safety gates, and recovery procedures for synchronizing the hosted Supabase database with the canonical Alembic migration chain.

In strict compliance with **Non-Negotiable Rule 0**:
- **Never Blindly Run Migrations:** Migrations are never executed without pre-flight state validation.
- **Data Preservation Guarantee:** Existing data must never be truncated or overwritten.
- **Alembic as Authority:** Alembic remains the sole migration authority; the migration artifact `database/migrations/complete_hosted_schema.sql` is deterministically compiled from Alembic revisions `001_initial_schema` and `002_messaging_realtime`.

---

## 2. Alembic Migration Chain Architecture

```
[None] 
  │
  ▼ (001_initial_schema)
  ├── Extensions (uuid-ossp, pg_trgm)
  ├── 35 Core Identity, Property, Matching & Lifestyle Tables
  │
  ▼ (002_messaging_realtime) [HEAD]
  ├── Conversations context columns (title, application_id, group_id, flatmate_match_id)
  ├── Messaging subsystem (attachments, read cursors, preferences, outbox_events)
  └── Indexes, foreign keys, and cascading rules
```

- **Current Revision in Reference DB:** `002_messaging_realtime`
- **Down Revisions:** Reversible DDL with `downgrade()` functions implemented in both migration files.
- **Deterministic DDL Bundle:** `database/migrations/complete_hosted_schema.sql` contains the complete idempotent DDL transaction matching revision `002_messaging_realtime`.

---

## 3. Migration Execution Protocol for Hosted Supabase

Due to the local network perimeter blocking outbound direct PostgreSQL TCP ports 5432/6543, migrations are deployed via one of two authorized, secure methods:

### Option A: Supabase Dashboard SQL Editor (Primary Cloud Execution)
1. Navigate to `https://supabase.com/dashboard/project/qjwitdovbsfviaepjcul/sql`.
2. Open `database/migrations/complete_hosted_schema.sql` in the Flatmate repository.
3. Paste the complete SQL script into the SQL Query Editor.
4. Click **Run**.
5. Execution executes inside a single `BEGIN; ... COMMIT;` transaction. If any syntax or constraint error occurs, the entire migration rolls back automatically without partial state contamination.
6. PostgREST immediately reloads its schema cache upon completion.

### Option B: CI/CD Staging Deployment Pipeline (Automated Wire Execution)
1. Triggered via `.github/workflows/staging-deploy.yml`.
2. GitHub Actions Ubuntu runner (which has unrestricted outbound 5432) executes:
   ```bash
   alembic -c apps/api/alembic.ini upgrade head
   ```
3. Verifies `alembic current` matches `002_messaging_realtime`.

---

## 4. Pre-Flight and Post-Flight Verification Checklist

| Step | Gate Description | Verification Command / Query | Pass Criteria |
| :---: | :--- | :--- | :--- |
| **Pre-1** | Verify Project Health | `GET /auth/v1/settings` | HTTP 200 |
| **Pre-2** | Check Public Schema | `GET /rest/v1/` | Schema reachable |
| **Pre-3** | Backup Existing State | Supabase Dashboard $\to$ Database $\to$ Backups | Backup snapshot confirmed |
| **Post-1**| Verify Alembic Table | `SELECT version_num FROM alembic_version;` | Returns `002_messaging_realtime` |
| **Post-2**| Verify Table Count | `SELECT count(*) FROM information_schema.tables WHERE table_schema='public';` | Exactly 43 tables |
| **Post-3**| Verify FK Integrity | `SELECT count(*) FROM information_schema.table_constraints WHERE constraint_type='FOREIGN KEY';` | Exactly 69 foreign keys |
| **Post-4**| PostgREST Schema Cache | `GET /rest/v1/` | 42 resource definitions exposed |

---

## 5. Rollback Runbook

If any anomaly occurs during post-flight verification:
1. **Immediate Transaction Rollback:** The migration script runs in a `BEGIN; ... COMMIT;` block; unhandled runtime exceptions trigger an immediate PostgreSQL transaction rollback.
2. **Point-In-Time Restore (PITR):** Supabase daily physical backups can restore the database instance to the pre-migration snapshot in the Supabase Dashboard.
3. **Controlled Down Migration:**
   ```bash
   alembic -c apps/api/alembic.ini downgrade 001_initial_schema
   ```
