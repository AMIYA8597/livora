# Phase 20 Monitoring, Observability & Alerting Architecture

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** Site Reliability Engineer (SRE)  

---

## 1. Observability Stack & Health Probes

The staging infrastructure integrates a multi-tier telemetry stack designed to give real-time visibility into application performance, availability, and error budgets:

| Tier | Tool / Telemetry Source | Monitored Metrics & Indicators | Normal Baseline |
|---|---|---|---|
| **API Health** | Google Cloud Monitoring | Liveness (`/health`), container CPU/RAM utilization, request count, HTTP 4xx/5xx status codes. | HTTP 200, < 25% CPU, < 150MB RAM |
| **Response Latency** | Cloud Run Metrics / Uptime Probes | p50, p95, p99 round-trip latency. | p50 < 45ms, p95 < 120ms |
| **Edge Frontend** | Vercel Analytics & Speed Insights | Core Web Vitals (LCP, FID, CLS), edge cache hit ratio, build duration. | LCP < 1.8s, CLS < 0.05 |
| **Database Telemetry** | Supabase Dashboard & pg_stat_statements | Active connections, pool exhaustion, query execution duration, cache hit ratio. | Cache hit > 98%, active pool < 8 |
| **Application Logging** | Google Cloud Logging (`stdout` JSON format) | Structured exception traces, correlation IDs, user action logs (masked). | 0 unhandled 500 exceptions |

---

## 2. Health Endpoint Specification

The backend exposes a multi-component health probe at `/health`:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "staging",
  "checks": {
    "database": "connected",
    "postgis": "available",
    "vector": "available",
    "storage": "accessible"
  },
  "timestamp": "2026-11-13T18:30:00Z"
}
```
If any required subsystem fails to respond within 2.0 seconds, the status degrades to `"unhealthy"` with an HTTP 503 response, alerting monitoring probes.

---

## 3. Alerting Thresholds & Notification Channels

| Metric / Event | Severity | Alert Trigger Condition | Escalation Channel | Immediate Remediation |
|---|---|---|---|---|
| **High Error Rate** | Critical (P1) | HTTP 5xx rate > 2% over 5-minute window | Slack `#alerts-staging` + Email | Trigger immediate automated rollback. |
| **Latency Degradation** | High (P2) | p95 latency > 800ms for 3 consecutive minutes | Slack `#alerts-staging` | Inspect slow database queries and scaling limits. |
| **Database Pool Saturation** | High (P2) | Pool utilization > 85% for > 2 minutes | Slack `#alerts-staging` | Investigate lingering unclosed sessions or spike. |
| **Container Memory Warning** | Medium (P3) | Memory usage > 80% (410MB / 512MB) | Email to DevOps | Check for memory leaks in heavy vector calculations. |
| **Budget Alert** | Medium (P3) | Monthly staging spend projected to exceed $15 | Email to Account Owner | Scale down idle replicas, inspect runaway storage usage. |
