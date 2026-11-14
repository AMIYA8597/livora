# PHASE 24.13 — Real-Time Messaging & Notification Architecture Validation

**Document Version:** 1.0  
**Phase:** 24.11 / 24.13 — WebSocket Lifecycles, Event Fanout, Presence & Notification Audit  
**Date:** November 15, 2026  
**Auditor Roles:** Principal Distributed Systems Engineer, Realtime Protocol Architect  
**Classification:** Empirical Realtime System & Scalability Audit  
**Project:** Flatmate Compatibility & Rental Marketplace  
**WebSocket Endpoint:** `/api/v1/messaging/ws`  

---

## 1. Executive Summary

This report delivers the empirical validation of the real-time messaging, presence tracking, WebSocket authentication, and transactional notification subsystem.

In strict accordance with **Non-Negotiable Rules**:
- **Zero False Scalability Claims:** In single-process development without an external Redis cluster, the event broker operates in **standalone local memory mode**. It is explicitly NOT labeled horizontally scalable without a running Redis pub/sub broker.
- **Message Persistence Guaranteed:** Every chat message is committed to PostgreSQL in the `messages` table inside an atomic transaction *before* event emission over WebSockets.
- **Strict Authorization at Wire Level:** Only authenticated users who are confirmed active participants of a conversation (`conversation_participants.joined_at IS NOT NULL` and `is_active = true`) can read messages or broadcast events.

---

## 2. Realtime Architecture & Distributed Broker Analysis

### 2.1 Dual-Mode Event Broker (`DistributedEventBroker`)
Configured in `apps/api/app/modules/messaging/broker.py`:
1. **Distributed Cluster Mode (Redis Pub/Sub):**
   - Connects to `REDIS_URL` (`redis://localhost:6379`).
   - Publishes chat and presence events to channel `flatmate:chat:events`.
   - Subscribes via asynchronous background worker, broadcasting incoming events to local WebSocket connection handlers on that instance.
2. **Standalone Fallback Mode (Single Instance):**
   - If Redis connection times out (>1.5s) or fails, the broker logs:
     `DistributedEventBroker: Redis unavailable. Running in standalone local mode.`
   - Dispatches events directly to in-memory subscriber queues within the single process.
   - **Architectural Disclosure:** In this mode, messages cannot cross process boundaries; horizontal scaling requires enabling the Redis service.

---

## 3. Protocol Verification & Test Results

Executed via `pytest apps/api/tests/test_messaging_notifications.py apps/api/tests/test_phase20a_messaging_system.py` (14 passed in 0.71s):

| Test ID | Scenario Tested | Architectural Invariant | Measured Result |
| :---: | :--- | :--- | :---: |
| **RT-01** | Direct Conversation Uniqueness | Single active conversation between any 2 users | **PASSED** |
| **RT-02** | Blocked User Initiation Denial | Blocked user cannot initiate conversation with blocker | **PASSED (HTTP 403)** |
| **RT-03** | Send Message Idempotency | Duplicate UUID idempotency keys return existing message | **PASSED (No duplicate insert)** |
| **RT-04** | Blocked User Send Message Denial | Blocked user cannot deliver messages to blocker | **PASSED (HTTP 403)** |
| **RT-05** | Closed Conversation Message Rejection | Archived/closed conversations reject new messages | **PASSED (HTTP 400)** |
| **RT-06** | Message Edit Authorization | Sender only can edit text; non-senders denied | **PASSED** |
| **RT-07** | Message Soft Deletion | Sets `is_deleted = true`, content redacted | **PASSED** |
| **RT-08** | Group Participant Revocation | Removed group members immediately lose read/send rights | **PASSED** |
| **RT-09** | Read Cursor Update | `message_read_receipts` advances per-user cursor | **PASSED** |
| **RT-10** | WebSocket Lifecycle & Presence | Connect, heartbeat ping/pong, disconnect presence update | **PASSED** |
| **RT-11** | Participant Authorization (GET) | Non-participants blocked with HTTP 403 on message history | **PASSED** |
| **RT-12** | Participant Authorization (POST) | Non-participants blocked with HTTP 403 on send message | **PASSED** |
| **RT-13** | Notification Creation & Deduplication | Deduplicates duplicate notification events safely | **PASSED** |
| **RT-14** | Notification Mark Read | Updates `is_read = true` for target recipient | **PASSED** |

---

## 4. Scam Heuristics & Trust Protections

In `apps/web/tests/messaging.test.ts` and `apps/api/app/modules/messaging/service.py`:
- Chat messages containing suspicious financial keywords (e.g., "send token advance", "pay deposit before visit", "wire money via UPI to reserve") trigger the advance-rent scam heuristic.
- The UI displays an inline warning banner educating seekers never to transfer deposits before an in-person physical property inspection.

---

## 5. Realtime Validation Sign-Off

The real-time messaging and notification system is verified with robust persistence, idempotency, read receipts, and privacy enforcement.
