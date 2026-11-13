# Phase 19 — Observability, Structured Logging & Telemetry Report

**Project:** Flatmate Compatibility & Rental Marketplace  
**Document ID:** `OBS-19-OSR-01`  
**Phase:** 19 — Full-System Quality Assurance, Adversarial Security Testing & Release Candidate Verification  
**Evaluation Standard:** 12-Factor App Observability, RFC 7807 Problem Details, Distributed Tracing  
**Author:** Principal DevSecOps & SRE Lead  
**Date:** November 2026  
**Status:** VALIDATED & BASELINED  

---

## 1. Executive Summary

This report defines and validates the observability architecture across the Flatmate platform. The system implements a three-pillar observability framework consisting of structured JSON logging with strict PII redaction, distributed correlation tracing via `X-Request-ID`, and health/readiness telemetry probes.

---

## 2. Distributed Tracing & Request ID Lifecycle

The platform enforces end-to-end request tracing via `RequestTraceAndSecurityMiddleware` (`apps/api/app/core/middleware.py`):

```
Client / Edge Proxy
        |  (Injects or propagates X-Request-ID)
        v
FastAPI Middleware
        |  (Stores request_id in request.state.request_id)
        |  (Starts microsecond wall-clock timer)
        +-----------------------------------+
        |                                   |
        v                                   v
Application Service Layer            Structured Log Stream
(Includes request_id in queries)    [Req <uuid>] JSON entry
        |                                   |
        v                                   v
HTTP Response Headers                Background Celery Task
X-Request-ID: <uuid>                 task.apply_async(headers={"request_id": <uuid>})
X-Process-Time-Ms: 14.25
```

### Trace Header Contract:
- `X-Request-ID`: Canonical UUIDv4 tracing identifier returned on all responses.
- `X-Process-Time-Ms`: High-precision execution duration in milliseconds.
- `Content-Length` enforcement: Requests $> 10\text{ MB}$ rejected with HTTP 413 `Payload Too Large`.

---

## 3. Structured Logging & Sensitive Data Redaction

### 3.1 JSON Log Schema
All application log records conform to the following schema:
```json
{
  "timestamp": "2026-11-13T18:22:38.125Z",
  "level": "INFO",
  "service": "flatmate-api",
  "request_id": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
  "method": "POST",
  "path": "/api/v1/applications/",
  "status_code": 201,
  "duration_ms": 28.45,
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "client_ip": "103.21.244.0",
  "message": "Application created successfully"
}
```

### 3.2 Sensitive Data Redaction Policy
To prevent PII leaks into log ingestion pipelines (e.g. Datadog, CloudWatch, Loki):
1. **Passwords & Tokens:** Query strings, headers, and request bodies matching `password`, `token`, `secret`, `access_token`, `refresh_token`, or `authorization` are filtered prior to logging.
2. **Aadhaar Numbers:** Regex pattern `\b\d{4}\s?\d{4}\s?\d{4}\b` is automatically masked as `XXXX-XXXX-1234`.
3. **PAN Cards:** Regex pattern `[A-Z]{5}[0-9]{4}[A-Z]{1}` is masked as `XXXXX1234X`.
4. **Phone Numbers:** Masked as `+91 98**** *123`.

---

## 4. Health & Telemetry Probes

The API exposes specialized health endpoints designed for Kubernetes / container orchestrator probes:

| Route | HTTP Method | Probe Type | Checked Subsystems | Expected Response |
| :--- | :--- | :--- | :--- | :--- |
| `/health` | GET | Liveness | HTTP Server process responsiveness | `{"status": "healthy", "service": "...", "version": "1.0.0"}` (200 OK) |
| `/health/live` | GET | Liveness | Identical alias for Kubernetes `livenessProbe` | `{"status": "healthy"}` (200 OK) |
| `/ready` | GET | Readiness | Database ping & cache availability | `{"status": "ready", "database": "connected", "cache": "operational"}` (200 OK) |
| `/health/ready`| GET | Readiness | Identical alias for Kubernetes `readinessProbe` | `{"status": "ready"}` (200 OK) |

---

## 5. RFC 7807 Standard Error Formatting

All uncaught exceptions and application errors are intercepted and formatted according to RFC 7807 (`application/problem+json`):

```json
{
  "type": "https://errors.flatmate.platform/forbidden",
  "title": "Forbidden",
  "status": 403,
  "detail": "You do not have permission to modify this property.",
  "instance": "/api/v1/properties/6b29fc40-62c8-4e17-b649-41710ec163b2",
  "request_id": "8f8832a8-f716-43b5-bb8a-40a2a4b8682a"
}
```

---

## 6. Alerting Thresholds & Monitoring Rules

| Alert Name | Evaluation Metric | Threshold | Action Triggered |
| :--- | :--- | :--- | :--- |
| **HighErrorRate5xx** | 5xx errors / total requests | $> 1\%$ over 5 minutes | Page on-call engineer (P1) |
| **P95LatencyDegradation**| p95 request duration | $> 500\text{ ms}$ over 10 minutes | Slack channel alert (P2) |
| **DatabasePoolStarvation**| Active pool connections / total pool | $> 85\%$ over 3 minutes | Trigger horizontal autoscaling (P2) |
| **WebSocketDisconnectSpike**| Reconnection rate | $> 200\text{ reconnects/sec}$ | Alert SRE; investigate network partition |

---

## 7. Observability Verdict

The observability architecture provides full auditability, correlation tracing across distributed boundaries, RFC 7807 error standardization, and proactive health detection.

**Observability Gate Status: APPROVED FOR STAGING.**
