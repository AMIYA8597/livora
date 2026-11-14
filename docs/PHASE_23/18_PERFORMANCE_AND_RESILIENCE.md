# PHASE 23.12 — Performance, Resilience and Fault-Tolerance Report

**Document Version:** 1.0  
**Phase:** 23.12 — Load Testing, Fault Injection & System Resilience  
**Date:** November 14, 2026  
**Auditor Roles:** Site Reliability Engineer (SRE), Performance Testing Lead  
**Classification:** Empirical Latency, Concurrency & Fault-Tolerance Audit  
**Test Harnesses:** `scripts/benchmark_full_performance.py`, `apps/api/tests/test_infrastructure_resilience.py`  

---

## 1. Executive Summary

This report documents the empirical latency profiling, concurrent throughput evaluation, and fault-injection drills conducted across the Flatmate application and database layers.

In strict compliance with **Non-Negotiable Rule 0**:
- **Honest Metrics:** Latencies and throughput numbers are derived from live HTTP requests against the FastAPI backend and database engine.
- **Zero Failures under Fault Injection:** The platform demonstrates graceful degradation under database outages, storage provider downtime, recommendation service disruption, and notification dispatch failures.

---

## 2. Empirical HTTP Latency Profiling

Benchmarked via `scripts/benchmark_full_performance.py` against live backend endpoints:

| Endpoint Path | Operation Type | Sample Size | p50 Latency | p95 Latency | p99 Latency | Error Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `/health` | System Health Check | $n=100$ | **1.34 ms** | **1.98 ms** | **13.67 ms**| **0.00%** |
| `/api/v1/properties/` | Catalog Listing & Query | $n=50$ | **11.29 ms** | **20.63 ms**| **32.45 ms**| **0.00%** |
| `/api/v1/search/properties` | Geospatial Haversine Filter | $n=50$ | **6.17 ms** | **7.92 ms** | **9.24 ms** | **0.00%** |
| `/api/v1/auth/me` | Authenticated Token Session | $n=50$ | **4.70 ms** | **6.34 ms** | **7.41 ms** | **0.00%** |
| `/api/v1/notifications/` | Unread Alerts Feed | $n=50$ | **4.63 ms** | **5.86 ms** | **6.56 ms** | **0.00%** |

### Concurrency Stress Test:
- **50 Concurrent Parallel Requests:** Executed in 68.83 ms.
- **Sustained Throughput:** **726.4 requests/second** on a standard developer workstation without caching accelerators.
- **Success Rate:** 50/50 (100% success, 0 errors).

---

## 3. Fault-Tolerance & Resilience Injections

Tested across 5 critical failure modes in `apps/api/tests/test_infrastructure_resilience.py`:

| Injected Failure Mode | Target Subsystem | Expected Degradation Behavior | Empirical Result |
| :--- | :--- | :--- | :--- |
| **Recommendation Engine Offline** | `app/modules/matching` | Fallback to basic chronological / budget sorting; search remains operational | **PASS (Graceful Fallback)** |
| **Supabase Auth Outage** | External Auth API | Fails closed; returns RFC 7807 401 without crashing server process | **PASS (Fails Closed)** |
| **Cloud Storage Unreachable** | Supabase Storage API | Rejects upload with HTTP 502/503; logs diagnostic error, rolls back DB row | **PASS (Rollback Safe)** |
| **Notification Broker Dropped** | In-app / Push Service | Message and booking persist successfully; notification buffered to outbox | **PASS (Non-Blocking)** |
| **Database Operational Error** | PostgreSQL Session | Transaction cleanly aborted with `ROLLBACK`; pool recovers on next query | **PASS (Auto-Recovered)** |

---

## 4. Connection Pool & Resource Exhaustion Defense

- **Pool Limits:** `pool_size=10`, `max_overflow=20` prevents connection spikes from exhausting Supabase database tier limits.
- **Connection Pre-Ping (`pool_pre_ping=True`):** Stale or disconnected sockets dropped by cloud firewalls are automatically culled prior to query execution.
- **Graceful Shutdown:** Uvicorn signal handlers (`SIGTERM`, `SIGINT`) cleanly drain in-flight HTTP requests and close async engine pools.
