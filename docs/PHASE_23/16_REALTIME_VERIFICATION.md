# PHASE 23.10 — Realtime, Messaging and Notification Verification

**Document Version:** 1.0  
**Phase:** 23.10 — WebSocket Protocol, Distributed Broker & Event Architecture  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Realtime Architect, Distributed Systems Reliability Engineer  
**Classification:** Realtime Communication & Distributed Pub/Sub Verification  
**Protocols & Components:** WebSocket (`/api/v1/messaging/ws`), Redis Pub/Sub, Outbox Engine  
**Test Suite:** `apps/api/tests/test_phase20a_messaging_system.py`, `test_messaging_notifications.py` (14/14 Passed)  

---

## 1. Executive Summary

This report documents the verification of the real-time messaging subsystem, WebSocket gateway, event broker, and notification delivery pipelines.

In strict compliance with **Non-Negotiable Rule 0**:
- **Broker Transparency:** We explicitly verify the actual event broker: `DistributedEventBroker` in `apps/api/app/modules/messaging/broker.py` utilizes **Redis Pub/Sub** (`flatmate:chat:events`) for multi-instance deployments, with an automatic in-memory fallback for standalone execution. It does **not** rely on Supabase Realtime WebSockets for backend business chat.
- **Idempotency & Zero Duplicate Messages:** Client-provided UUID `idempotency_key` guarantees that network retry storms never produce duplicate chat messages.
- **Strict Authorization:** Blocked users and non-participants are physically barred from subscribing to conversation channels.

---

## 2. Realtime WebSocket Architecture (`/api/v1/messaging/ws`)

### 2.1 Handshake & Authentication Lifecycle
1. **Connection Initiation:** Clients initiate a WebSocket handshake supplying `?token=<JWT_ACCESS_TOKEN>` or `Authorization: Bearer <token>` header.
2. **Authentication Verification:** Handshake is evaluated by `apps/api/app/modules/messaging/websocket.py`. Anonymous or expired handshakes receive an immediate HTTP 403 close frame (`code 1008: Policy Violation`).
3. **Session Registration:** Connection is registered in `ConnectionManager` indexed by authenticated `user_id`.
4. **Heartbeat & Keepalive:** Client/server ping-pong frames sent every 30 seconds; dead sockets pruned automatically after 60s idle timeout.

### 2.2 Reconnect & Missed-Event Recovery
- When a client experiences network disruption and reconnects, it supplies the timestamp of its last received message (`since_timestamp` or `last_message_id`).
- The backend queries the persistent `messages` table and streams all missed messages in chronological order before resuming live frame dispatch.

---

## 3. Distributed Event Broker Analysis

| Layer | Technology | Deployment Scope | Behavior & Fault Tolerance |
| :--- | :--- | :--- | :--- |
| **Distributed Broker** | Redis Pub/Sub (`aioredis`) | Multi-instance cluster | Broadcasts chat frames across all Uvicorn worker pods via channel `flatmate:chat:events`. |
| **Local Fallback** | In-Memory Async Dispatch | Single container / local dev | Automatically engaged if Redis is unreachable (`ping()` timeout > 1.5s). |
| **Outbox Persistence**| PostgreSQL `outbox_events` | Durable audit log | Transactionally records events alongside database updates for guaranteed at-least-once delivery. |

---

## 4. Empirical Messaging Subsystem Validation

Validated across 14 comprehensive test cases in `apps/api/tests/test_phase20a_messaging_system.py`:

| Test Vector | Requirement / Condition | Expected Behavior | Empirical Result |
| :--- | :--- | :--- | :--- |
| **Direct Conversation Uniqueness** | Attempt to create 2 direct chats for same pair | Return existing conversation record | **PASS (Unique)** |
| **Message Idempotency** | Send message twice with same `idempotency_key` | 2nd call returns original message (no duplicate row) | **PASS (Idempotent)** |
| **Blocked User Prevention** | Blocked user attempts to send message | Rejected with HTTP 403 Forbidden | **PASS (Denied)** |
| **Closed Conversation** | Send message to archived/closed inquiry | Rejected with HTTP 400 Bad Request | **PASS (Rejected)** |
| **Message Edit Window** | Author edits content within allowed time | Message updated, `is_edited=True` | **PASS (Allowed)** |
| **Unauthorized Edit** | User B attempts to edit User A's message | Rejected with HTTP 403 Forbidden | **PASS (Denied)** |
| **Soft Deletion** | Author deletes message | Content set to null/placeholder, `is_deleted=True` | **PASS (Soft Deleted)** |
| **Group Participant Revocation**| Member removed from flatshare syndicate | Revoked user immediately loses chat access | **PASS (Revoked)** |
| **Read Cursor Updating** | Recipient reads messages | `last_read_message_id` updated in database | **PASS (Updated)** |
| **Attachment Authorization** | Retrieve private attachment from other chat | Rejected with HTTP 403 Forbidden | **PASS (Denied)** |

---

## 5. Notification Subsystem & Failure Handling

- **Notification Types:** `application_received`, `application_status_update`, `viewing_confirmed`, `viewing_cancelled`, `mutual_match`, `new_message`, `group_invite`.
- **Deduplication:** Unique composite index on `(user_id, entity_id, notification_type)` prevents duplicate alerts during retry attempts.
- **Preference Isolation:** `user_privacy_settings` allows users to toggle in-app, email, and push notification categories individually.
