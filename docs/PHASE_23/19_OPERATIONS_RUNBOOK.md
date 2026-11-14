# PHASE 23.12 — Production Operations and Incident Response Runbook

**Document Version:** 1.0  
**Phase:** 23.12 — SRE Operations, Incident Management & Disaster Recovery  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Site Reliability Engineer (SRE), Incident Commander  
**Classification:** Operational Runbook & Disaster Recovery Plan  

---

## 1. Executive Summary

This runbook establishes standard operating procedures (SOP), health monitoring thresholds, backup/restore procedures, recovery objectives, and incident response playbooks for the Flatmate platform.

---

## 2. Recovery Objectives & Backup Architecture

| Metric | Target Objective | Strategy & Implementation |
| :--- | :---: | :--- |
| **Recovery Time Objective (RTO)** | **$< 30 \text{ minutes}$** | Containerized ECS/Docker deployments with pre-built immutable container images. |
| **Recovery Point Objective (RPO)** | **$< 5 \text{ minutes}$** | Supabase automated continuous WAL archiving and daily automated snapshots. |
| **Database Snapshot Frequency** | Daily at 02:00 UTC | Managed Supabase automated backups retained for 7 days (Free) / 30 days (Pro). |
| **Point-In-Time Recovery (PITR)** | Supported | Available on Supabase Pro/Team compute tiers via write-ahead log replaying. |

### Restore Procedure:
1. In Supabase Dashboard, navigate to **Database** $\to$ **Backups**.
2. Select desired restore snapshot or PITR timestamp.
3. Click **Restore**. Database instance pauses momentarily and resumes in healthy state.
4. Verify schema parity using `scripts/reconcile_schema.py`.

---

## 3. Monitoring, Health Checks & Observability

### 3.1 Standard Health Endpoints
- **Liveness Probe:** `GET /health/live` (Returns HTTP 200 `{"status": "healthy"}`)
- **Readiness Probe:** `GET /health/ready` (Returns HTTP 200 `{"status": "ready", "database": "connected", "cache": "operational"}`)
- **Failure Condition:** If PostgreSQL or Redis disconnects, `/health/ready` returns HTTP 503, signaling container orchestrators to remove the instance from the load balancer.

### 3.2 Production Alerting Thresholds

| Metric | Warning Threshold | Critical Alert (P1) | Recommended Action |
| :--- | :---: | :---: | :--- |
| **API Error Rate (5xx)** | $> 1.0\%$ for 5 min | $> 5.0\%$ for 2 min | Inspect application exception logs, roll back recent deployment |
| **p95 Latency** | $> 250 \text{ ms}$ | $> 1,000 \text{ ms}$ | Check database connection pool and slow query locks |
| **DB Connection Pool** | $> 80\%$ utilization | $> 95\%$ utilization | Scale pool size or investigate connection leak |
| **Redis Memory** | $> 75\%$ capacity | $> 90\%$ capacity | Trigger cache eviction or scale Redis instance |

---

## 4. Incident Response Playbooks

### Playbook 1: Production Outage (P1)
1. **Declare Incident:** Assign Incident Commander, establish war room.
2. **Health Check Triage:** Curl `/health/ready` to isolate backend from database/cache failure.
3. **Rollback if Caused by New Release:**
   - Web frontend: Vercel / AWS Amplify instant rollback to previous deployment ID.
   - Backend API: Revert Docker image tag to previous stable digest:
     ```bash
     docker compose -f docker-compose.prod.yml pull api
     docker compose -f docker-compose.prod.yml up -d api
     ```
4. **Database Rollback:** If a migration failed, run Alembic downgrade:
   ```bash
   alembic downgrade -1
   ```

### Playbook 2: Secret Compromise Response
1. **Containment:** Immediately revoke the compromised key in Supabase Dashboard (Settings $\to$ API $\to$ Rotate Secret).
2. **Secret Replacement:** Update backend environment variable `SUPABASE_SECRET_KEY` and restart API instances.
3. **Audit Token Abuse:** Inspect Supabase Auth logs for anomalous admin requests during the exposure window.
