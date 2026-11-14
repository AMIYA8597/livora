# PHASE 22.11 & 22.19 — Performance, Latency & Reliability Assessment

**Document Version:** 1.0  
**Phase:** 22.19 — Latency, Throughput & System Reliability Benchmarks  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Systems Architect, Database Performance Engineer, DevOps Lead  
**Classification:** Empirical Performance Benchmark Report  

---

## 1. Executive Summary

This report establishes the baseline performance and latency profiles for algorithmic computations and HTTP API endpoints in the Flatmate Compatibility & Rental Marketplace.

In accordance with Phase 22 non-negotiable guidelines:
- Benchmarks are **not** extrapolated to claim hypothetical production scalability; all figures reflect actual, reproducible measurements on the reference staging host.
- Both algorithmic kernel throughput (CPU operations/second) and end-to-end HTTP network roundtrips were benchmarked.

---

## 2. Test Environment & Baseline Specifications

- **Operating System:** Windows 11 Enterprise (64-bit, build 10.0.26100)
- **Processor / Runtime:** Multi-core x86_64 CPU running Python 3.13.7 with Uvicorn ASGI / uvloop.
- **Database Engine:** PostgreSQL 18.0 (MSVC 64-bit) with connection pooling (pool_size=10, max_overflow=20).
- **Test Dataset:** 96 physical properties, 10 user profiles, 43 relational tables.

---

## 3. Algorithmic Kernel Benchmarks

Measured via `scripts/test_performance_benchmarks.py` using `time.perf_counter()` and `psutil`:

| Algorithmic Subsystem | Iterations | Total Duration | Throughput (ops/sec) | Latency p50 | Latency p95 | Latency p99 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **10D Compatibility Engine** | 2,000 | 0.0346s | **57,728.2 ops/s** | **0.0152 ms** | **0.0287 ms** | **0.0393 ms** |
| **Haversine Distance + BBox** | 10,000 | 0.0624s | **160,204.8 ops/s**| **0.0051 ms** | **0.0098 ms** | **0.0142 ms** |
| **Group Syndicate (6 persons)**| 500 groups (7,500 pairs) | 0.1084s | **4,612.3 groups/s** (69,184.7 pairs/s) | **0.2012 ms** | **0.3120 ms** | **0.4280 ms** |

### Memory & Stability:
- **Baseline Memory RSS:** 158.47 MB
- **Final Memory RSS after 2,000 iterations:** 158.57 MB (Delta: **+0.10 MB**).
- Zero memory leakage detected; garbage collection reclaimed temporary factor dictionary allocations cleanly.

---

## 4. Live HTTP API Endpoint Latencies

Measured via `scripts/benchmark_api_latency.py` over 100 consecutive HTTP requests to the live backend on port 8001:

| API Route | Method | Sample Size | Mean Latency | p50 (Median) | p95 Latency | p99 Latency | Error Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`/health` (Liveness Probe)** | `GET` | $n=100$ | 3.31 ms | **2.93 ms** | **5.67 ms** | **7.25 ms** | 0.0% |
| **`/api/v1/properties` (Catalog)**| `GET` | $n=100$ | 16.53 ms | **15.39 ms** | **22.43 ms** | **34.05 ms**| 0.0% |
| **`/api/v1/search/properties` (Geospatial)**| `POST` | $n=100$ | 11.16 ms | **10.15 ms** | **20.24 ms** | **26.45 ms**| 0.0% |

---

## 5. Reliability & Failure Modes

1. **Transient Database Disconnects:**
   The async engine (`create_async_engine`) is configured with `pool_pre_ping=True`, testing connection validity before leasing sessions from the pool.
2. **WebSocket Keep-Alive & Auto-Reconnect:**
   The frontend `useSocket` client dispatches a heartbeat ping every 25 seconds. Connections experiencing unexpected closure initiate exponential backoff reconnection (1s, 2s, 4s, 8s, up to max 30s).
3. **Graceful Fallbacks:**
   - Vector search falls back to keyword token search if vector extensions are unavailable.
   - External ML reranker falls back to deterministic 10D compatibility engine if inference exceeds 3,000ms.
