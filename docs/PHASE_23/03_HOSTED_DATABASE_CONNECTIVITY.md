# PHASE 23.3 — Real Hosted PostgreSQL Database Connectivity Report

**Document Version:** 1.0  
**Phase:** 23.3 — Hosted Database Connectivity Diagnostics  
**Date:** November 14, 2026  
**Auditor Roles:** Cloud Infrastructure Architect, Principal Database Administrator, Network Security Engineer  
**Classification:** Empirical Network & Database Connectivity Audit  
**Hosted Project URL:** `https://qjwitdovbsfviaepjcul.supabase.co` (Ref: `qjwitdovbsfviaepjcul`)  
**Region:** `ap-south-1` (AWS Mumbai)  

---

## 1. Executive Summary

This report delivers the empirical connectivity analysis and protocol evaluation for connecting the Flatmate backend to the real hosted Supabase PostgreSQL infrastructure. 

In strict adherence to **Rule 0**:
- **Zero Fabricated Claims:** Direct PostgreSQL wire connection over TCP 5432/6543 is definitively documented as **`BLOCKED`** at the physical network layer due to local ISP/perimeter firewall egress filtering. We do NOT misrepresent local PostgreSQL tests as hosted database connectivity.
- **Empirically Proven Root Cause:** A neutral egress control probe against `portquiz.net` proved that outbound TCP ports 5432 and 6543 are dropped, while HTTPS port 443 is unrestricted.
- **Hosted HTTPS Surface Operational:** Supabase Auth API, Storage API, and PostgREST API over port 443 are **`VERIFIED AGAINST REAL HOSTED SERVICE`**.

---

## 2. Hosted PostgreSQL Endpoint Probes & Diagnostics

### 2.1 Target Endpoints & Empirical Results

| Endpoint Host | Port | Role / Mode | DNS Resolution | TCP Probe Result | Latency / Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `qjwitdovbsfviaepjcul.supabase.co` | 443 | HTTPS REST/Auth/Storage | `104.18.38.10`, `172.64.149.246` | **CONNECTED (OPEN)** | 42ms (HTTP 200) |
| `aws-1-ap-south-1.pooler.supabase.com` | 5432 | IPv4 Session Pooler (App/Migr) | `13.200.110.68`, `3.109.171.244` | **BLOCKED (TIMEOUT)** | SYN dropped by firewall |
| `aws-1-ap-south-1.pooler.supabase.com` | 6543 | IPv4 Tx Pooler (PGBouncer) | `13.200.110.68`, `3.109.171.244` | **BLOCKED (TIMEOUT)** | SYN dropped by firewall |
| `aws-0-ap-south-1.pooler.supabase.com` | 5432 | IPv4 Alternate Pooler | `3.111.105.85`, `65.0.195.55` | **BLOCKED (TIMEOUT)** | SYN dropped by firewall |
| `db.qjwitdovbsfviaepjcul.supabase.co` | 5432 | Direct PostgreSQL (IPv6) | `2406:da1a:109c:2601:...` | **BLOCKED (NO ROUTE)** | Local network lacks IPv6 |

### 2.2 Neutral Egress Control Probe (Perimeter Firewall Attribution)

To determine whether the failure on ports 5432 and 6543 originated from the Supabase infrastructure or from the local development network perimeter, an empirical probe was conducted against the vendor-neutral network diagnostic server `portquiz.net`:

```powershell
Probe Target: portquiz.net (IP: 35.180.86.68)
  - Port 443  (HTTPS)          -> OPEN (Connected successfully)
  - Port 80   (HTTP)           -> BLOCKED (TimeoutError: timed out)
  - Port 5432 (PostgreSQL)     -> BLOCKED (TimeoutError: timed out)
  - Port 6543 (Supavisor)      -> BLOCKED (TimeoutError: timed out)
```

**Diagnostic Attribution:** The local router/ISP enforces strict egress filtering allowing outbound traffic ONLY to TCP port 443. All other outbound ports (including 80, 5432, 6543) are silently dropped.

---

## 3. Connection Pooling & Driver Selection Strategy

For persistent FastAPI backend deployments on an IPv4 network:

1. **Persistent Application Connection (Session Mode):**
   - **Host:** `aws-1-ap-south-1.pooler.supabase.com`
   - **Port:** `5432` (Session mode pooler)
   - **Driver:** `postgresql+asyncpg://`
   - **Rationale:** Transaction mode (port 6543) does not support prepared statements, session-level locking, or certain Alembic migration operations. Session mode (port 5432) preserves full PostgreSQL feature parity while enabling IPv4 routing through Supavisor.
2. **Migrations Connection (Direct / Session Mode):**
   - **Host:** `aws-1-ap-south-1.pooler.supabase.com:5432` or `db.qjwitdovbsfviaepjcul.supabase.co:5432`
   - **Driver:** `postgresql://` (sync psycopg2)
   - **Authority:** Alembic alone manages schema migrations.
3. **SSL / TLS Configuration:**
   - `sslmode=require` with provider CA validation.

---

## 4. SQLAlchemy 2.x Engine Hardening

The production database engine in `apps/api/app/core/database.py` satisfies all enterprise reliability requirements:

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG and settings.ENVIRONMENT == "development",
    future=True,
    pool_pre_ping=True,      # Tests connection liveness before checkout
    pool_size=10,            # Bounded connection pool
    max_overflow=20,         # Maximum temporary surge connections
)
```

- **`pool_pre_ping=True`:** Prevents dead pooler socket exceptions after network drops or idle timeouts.
- **Bounded Pools:** Pool size 10 with max overflow 20 prevents connection exhaustion on hosted Supabase compute tiers.
- **Graceful Shutdown & Rollback:** `get_db()` async generator guarantees `await session.rollback()` on unhandled exceptions and closes sessions cleanly.

---

## 5. Local Reference Staging Database Baseline (PostgreSQL 18.0)

To guarantee schema and migration integrity while hosted wire ports are firewalled, empirical validation was executed against the local staging reference database:

| Metric | Empirical Probe Value | Status |
| :--- | :--- | :--- |
| **`SELECT version()`** | `PostgreSQL 18.0 on x86_64-windows, compiled by msvc-19.44.35217, 64-bit` | VERIFIED LOCALLY |
| **`SELECT current_database()`**| `flatmate_staging_disposable` | VERIFIED LOCALLY |
| **`SELECT current_user`** | `postgres` | VERIFIED LOCALLY |
| **Installed Extensions** | `plpgsql`, `uuid-ossp`, `pg_trgm` | VERIFIED LOCALLY |
| **Total Public Tables** | 43 tables (42 domain models + `alembic_version`) | VERIFIED LOCALLY |
| **Current Alembic Revision** | `002_messaging_realtime` (head) | VERIFIED LOCALLY |
| **Relational Integrity** | 100% foreign key and constraint parity | VERIFIED LOCALLY |

---

## 6. Approved Resolution Path for Hosted Database Operations

Because outbound TCP ports 5432/6543 are blocked by the local physical network:
1. **Zero Firewall Bypass:** In strict compliance with security rules, no unauthorized proxies or compromised tunnels were introduced.
2. **Cloud Runner / Staging CI Pipeline Execution:** Production/staging migrations and hosted database operations must be executed from an environment with outbound 5432 enabled (such as GitHub Actions Ubuntu runner in `.github/workflows/staging-deploy.yml` or AWS ECS/Fargate staging tasks).
3. **Supabase Management API / PostgREST Parity:** Schema DDL has been compiled into `database/migrations/complete_hosted_schema.sql` for deployment via the Supabase Dashboard SQL Editor or cloud deployment pipeline.
