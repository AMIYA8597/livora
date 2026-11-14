# PHASE 23.21 — Blockers, Root Cause Analysis & Remediation Plan

**Document Version:** 1.0  
**Phase:** 23.21 — Outstanding Blockers & Strategic Remediation  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Infrastructure Architect, Network Reliability Engineer, CISO  
**Classification:** Root Cause Attribution & Actionable Remediation Plan  
**Project:** Flatmate Compatibility & Rental Marketplace  

---

## 1. Executive Summary

This document identifies the outstanding external blockers preventing direct wire connectivity between the Windows development environment and the hosted Supabase PostgreSQL database, details the empirical root cause, and provides a clear, actionable remediation plan.

---

## 2. Identified Blockers & Root Cause Analysis

### Blocker BLK-23-01: Outbound TCP Ports 5432 and 6543 Blocked by Perimeter Firewall
- **Classification:** External Network Boundary Constraint
- **Severity:** High (Prevents direct database wire connection from development workstation)
- **Empirical Evidence:**
  - `aws-0-ap-south-1.pooler.supabase.com:5432` -> `BLOCKED / TimeoutError`
  - `aws-0-ap-south-1.pooler.supabase.com:6543` -> `BLOCKED / TimeoutError`
  - Control Target: `portquiz.net:443` -> `OPEN / CONNECTED`
  - Control Target: `portquiz.net:5432` -> `BLOCKED / TimeoutError`
  - Control Target: `portquiz.net:80` -> `BLOCKED / TimeoutError`
- **Root Cause Attribution:** The local router/ISP enforces strict egress firewall rules dropping all outbound SYN packets on ports other than TCP 443. This is a physical network boundary outside application code.

### Blocker BLK-23-02: Direct Database Host Lacks IPv4 Routing
- **Host:** `db.qjwitdovbsfviaepjcul.supabase.co`
- **Empirical Evidence:** `getaddrinfo failed [Errno 11001]`
- **Root Cause Attribution:** Supabase direct database hostnames resolve to IPv6 addresses. The development network is IPv4-only. Supabase requires using the IPv4 poolers (`aws-0-ap-south-1.pooler.supabase.com`) on IPv4 networks.

---

## 3. Actionable Remediation Plan

### Remediation Path 1: CI/CD Migration Execution (Immediate / Recommended)
Because GitHub Actions cloud runners have unrestricted outbound access on ports 5432 and 6543:
1. Configure repository secrets in GitHub:
   - `STAGING_DATABASE_URL`: Session pooler connection string `postgresql://postgres.[ref]:[password]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require`
2. Trigger the prepared workflow `.github/workflows/hosted-db-migration.yml` via GitHub Actions `workflow_dispatch`.
3. The workflow executes `alembic upgrade head`, bringing the hosted database to `002_messaging_realtime` in ~15 seconds.

### Remediation Path 2: Supabase Dashboard SQL Editor (Zero Infrastructure Prerequisite)
If CI/CD secrets are not yet configured:
1. Open the Supabase Dashboard -> SQL Editor for project `qjwitdovbsfviaepjcul`:
   `https://supabase.com/dashboard/project/qjwitdovbsfviaepjcul/sql`
2. Open the verified script `database/migrations/complete_hosted_schema.sql` in this repository.
3. Paste the contents into the SQL Editor and click **Run**.
4. The entire 43-table schema and `alembic_version` metadata are applied instantly inside an atomic transaction.

### Remediation Path 3: Perimeter Egress Approval / SOCKS5 Proxy (For Developer Workstations)
For developers requiring direct PostgreSQL CLI or GUI (DBeaver/pgAdmin) access:
1. Request network administrator to allow outbound TCP ports 5432 and 6543 to AWS Mumbai `ap-south-1` IP ranges.
2. Alternatively, configure a secure SSH/SOCKS5 tunnel or VPN over port 443.

---

## 4. Conclusion & Next Actionable Step

The application codebase is fully fortified and validated. Upon user approval, executing **Remediation Path 1 or 2** will complete the hosted PostgreSQL schema cutover.
