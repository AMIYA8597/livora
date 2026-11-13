# Phase 20 Real-Time Messaging & Background Workers Architecture

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** Senior DevOps & Backend Deployment Engineer  

---

## 1. Real-Time WebSocket & Pub/Sub Architecture

The platform provides bidirectional, low-latency communication for real-time messaging, presence indicators, read receipts, and typing notifications:

```
[ Next.js Client ]
       ▲
       │ WebSocket (WSS) / HTTP fallback
       ▼
[ Cloud Run FastAPI Pod ]
       ▲
       │ Pub/Sub (Redis)
       ▼
[ Redis 7 Cluster (Upstash / Memorystore) ]
       ▲
       │ Pub/Sub
       ▼
[ Sibling Cloud Run Pods ]
```

### Components
1. **WebSocket Handler (`apps/api/app/modules/messaging/websocket.py`):**
   - Manages active client connections per user.
   - Enforces JWT validation during the initial WebSocket handshake before allowing message exchanges.
   - Supports heartbeat ping/pong frames every 30 seconds to detect dead connections across mobile and edge networks.
2. **Message Broker (`apps/api/app/modules/messaging/broker.py`):**
   - In single-pod or local staging setups: uses high-speed in-memory event queues.
   - In distributed multi-pod staging/production: uses Redis Pub/Sub channels (`flatmate:channel:{conversation_id}`) to fan out messages across all active pods regardless of which pod holds the recipient's socket connection.
3. **Idempotency & Deduplication:**
   - Client sends UUIDv4 `idempotency_key` with every message payload.
   - Database enforces uniqueness constraints on `(conversation_id, idempotency_key)`, guaranteeing zero duplicate messages during rapid mobile retries.

---

## 2. Background Task Execution & Worker Strategy

To maintain sub-100ms API response times, non-blocking asynchronous operations are dispatched to background workers:
- **FastAPI `BackgroundTasks`:** Used for immediate lightweight tasks (email notifications, audit log writes, push notification dispatch).
- **Scheduled Housekeeping (Cloud Scheduler + Worker Route):**
  - Staging invokes `/api/v1/internal/housekeeping` on a cron schedule (`0 3 * * *` at 3:00 AM IST) via Google Cloud Scheduler.
  - Tasks executed:
    1. Soft-deleted message purging past retention period (30 days).
    2. Expired viewing appointment status rollover (`pending` -> `expired` if scheduled time passes without host action).
    3. Ephemeral presence and typing state garbage collection in Redis.
