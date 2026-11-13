# PHASE 20A — REAL-TIME MESSAGING, CHAT, GROUP COMMUNICATION AND NOTIFICATION SYSTEM AUDIT

**Audit Date:** November 2026  
**System:** Flatmate Compatibility & Rental Marketplace  
**Phase:** 20A — Real-Time Communication Engineering  
**Scope:** Complete repository audit of existing messaging, real-time transport, storage, moderation, notifications, contracts, and frontend components.

---

## 1. Executive Summary

A comprehensive repository audit was conducted across the backend (`apps/api`), frontend (`apps/web`), shared contracts (`packages/contracts`), database migrations, and infrastructure modules. While basic foundations for direct messaging and WebSocket connection were drafted in earlier phases, the existing implementation is **not production-ready** for a real-time, distributed, multi-participant rental marketplace.

Major vulnerabilities and gaps identified include:
1. **Process-Local WebSocket State:** WebSockets run on a local in-memory Python dictionary without distributed pub/sub (Redis/Realtime), breaking multi-worker and multi-instance deployments.
2. **Missing Safety & Blocking Enforcement:** `UserBlock` exists in the moderation module but is never queried during conversation creation or message sending; blocked users can freely message their blockers.
3. **No Idempotency or Deduplication:** Messages lack client idempotency keys, resulting in message duplication on network retries and reconnection.
4. **Primitive Data Model:** Missing attachments table, per-user read cursors, message editing/soft deletion, reply references, conversation context (application, match, PG enquiry, group roles), and conversation unique constraints.
5. **No Event Protocol or Validation:** WebSockets accept unversioned arbitrary JSON with no schema validation; typing indicators are no-ops (`pass`), and ping/pong heartbeats are missing.
6. **Frontend Gaps:** Inert controls, lack of pagination/virtualization, no attachment upload/preview, no group conversation management, no read receipt ticks, and lack of optimistic message reconciliation.

---

## 2. Detailed Findings by Module

### 2.1 Backend Messaging Module (`apps/api/app/modules/messaging/`)

| File | Implemented Features | Incomplete / Mock Features | Security & Architectural Defects |
| :--- | :--- | :--- | :--- |
| `models.py` | Basic `Conversation`, `ConversationParticipant`, `Message` | Missing `attachments`, `message_receipts`, `read_cursors`, `conversation_preferences`. Missing message reply-to, edit timestamp, deletion flag. | No unique constraint preventing duplicate 1-to-1 or context-linked conversations. Boolean `is_read` on `Message` fails completely for group messaging. |
| `service.py` | Basic listing, participant check, message insert, local broadcast | No message pagination cursor. No message edit/delete. No read receipt update. No block check. | In-memory message delivery. Race condition on concurrent conversation creation. Does not verify blocking or active group membership. |
| `router.py` | REST endpoints for listing, creating, and retrieving messages; WebSocket route | WebSocket endpoint accepts raw query token without handshake validation. No rate limiting. | IDOR risk: does not validate attachment access or context permissions. Lacks pagination parameters. |
| `websocket.py` | Local `ConnectionManager` with user-id-to-socket set | No heartbeat, no ping/pong, no backoff, no subscription authorization. | **Process-Local Only**: Breaks across multiple Uvicorn workers or multi-node Kubernetes pods. Global broadcast risk if not partitioned. |
| `schemas.py` | Basic request/response Pydantic schemas | Missing schemas for typing, read cursors, attachments, group actions, error envelopes. | Missing validation for message content length, injection sanitization, and UUID idempotency keys. |

### 2.2 Infrastructure & Real-Time Scalability (`apps/api/app/infrastructure/`)

1. **Redis Cache / PubSub (`infrastructure/cache.py`):**
   - Contains a standard Redis client with bypass mode.
   - **Defect:** Redis is currently only used as a key-value cache; Pub/Sub is not wired to WebSocket event dispatching.
   - **Requirement:** Implement a distributed `EventBroker` (Redis Pub/Sub with in-memory fallback for local development) to ensure horizontal scalability across multiple API replicas.

2. **Storage Provider (`infrastructure/storage.py` & `modules/storage/`):**
   - Supports local filesystem and Supabase Storage with signed URL generation.
   - **Defect:** Storage service does not enforce conversation-level authorization for chat attachments. Any authenticated user could request a signed URL for private attachments if the object path is known.
   - **Defect:** Lacks file magic-byte (signature) verification for uploads (only checks client-supplied MIME type).

### 2.3 Notifications (`apps/api/app/modules/notifications/`)

- Implements in-app notifications with a 5-minute idempotency window.
- **Defect:** Notifications are not broadcast in real time over the WebSocket connection (`notification.created` event is missing from the WebSocket transport).
- **Defect:** No user notification preferences (e.g. mute conversation, quiet hours, email channel toggle).

### 2.4 Safety, Moderation & Blocking (`apps/api/app/modules/moderation/`)

- Implements `UserBlock` and `ModerationReport`.
- **Defect:** Zero integration with `MessagingService`. Blocked users are not prevented from initiating conversations or sending messages.
- **Defect:** No automated link moderation, spam detection, or message rate-limiting.

### 2.5 Database Schema & Migrations

- Current Alembic migration (`001_initial_complete_schema.py`) creates minimal tables: `conversations`, `conversation_participants`, `messages`.
- **Missing Database Constraints:**
  - No partial unique index on `(type, property_id, least(p1, p2), greatest(p1, p2))` to prevent duplicate direct/property threads.
  - No `client_message_id` / `idempotency_key` unique constraint with conversation.
  - No `read_cursors` table for efficient unread count computation without row-by-row updates.
  - No `attachments` table with foreign keys, MIME verification, file size, and owner ID.

### 2.6 Shared Contracts (`packages/contracts/src/messaging.ts`)

- Contains only bare `ConversationDTO`, `MessageDTO`, and 4 WebSocket event strings.
- **Defect:** Completely missing the Phase 20A specified protocol:
  - `connection.ready`
  - `message.send`
  - `message.created`
  - `message.updated`
  - `message.deleted`
  - `message.delivered`
  - `message.read`
  - `typing.started`
  - `typing.stopped`
  - `presence.changed`
  - `conversation.updated`
  - `conversation.member_added`
  - `conversation.member_removed`
  - `notification.created`
  - `error`

### 2.7 Frontend Implementation (`apps/web/`)

1. **`ChatWindow.tsx`:**
   - Static 600px container; lacks mobile responsiveness and proper flex layout.
   - Regex-based client-side scam warning without server enforcement.
   - No attachment upload button, no typing indicators, no delivery/read checkmarks.
2. **`app/messages/page.tsx`:**
   - Conversation list displays hardcoded placeholders ("Flatmate Seeker / Host").
   - Lacks search, conversation filter tabs (All, Direct, Property, Groups), archive, and mute actions.
   - Missing unread counter badges.
   - No optimistic message delivery or error recovery state.
3. **`hooks/useSocket.ts`:**
   - No reconnection backoff with jitter.
   - Drops connection silently on network changes.
   - Cannot subscribe to specific conversations or send typed WebSocket frames.

---

## 3. Threat Model & Security Vulnerabilities

1. **IDOR on Message History & Attachments:** A non-participant could potentially read messages or private attachments if UUIDs were exposed or endpoints improperly checked. Server-side participant checks must be rigorously enforced on every single query.
2. **WebSocket Token Hijacking / Expiry:** WebSocket connections are not refreshed when the JWT expires; connection lifecycle must periodically re-validate or disconnect on token expiry.
3. **Spoofed Sender ID:** The WebSocket handler must bind `sender_id` strictly to the authenticated JWT `sub` claim, never trusting any client-provided sender ID.
4. **Denial of Service / Spam Bombing:** Absence of rate limiting on `message.send` allows automated scripts to overwhelm the database and connected sockets.
5. **Malicious File Uploads:** Lack of magic byte verification could allow executables disguised as images to be uploaded to storage.

---

## 4. Phase 20A Action Plan & Subphases

- **Subphase A: Audit and architecture (Completed)**
- **Subphase B: Database and migrations:** Implement normalized schema for conversations, members with roles, messages with idempotency, attachments, read cursors, outbox, and user preferences with Alembic migration.
- **Subphase C: Backend conversation services:** Complete business rules for 1-to-1, property, flatmate match, application, PG enquiry, and group conversations. Uniqueness enforcement.
- **Subphase D: Persistent message APIs:** Message sending with idempotency, editing, deletion, reply-to, pagination, and chronological ordering.
- **Subphase E: Authenticated WebSocket transport:** Versioned protocol (`v1`), JWT authentication, heartbeat, lifecycle management, and event validation.
- **Subphase F: Distributed event delivery:** Redis Pub/Sub event broker with in-memory fallback; outbox pattern for guaranteed durable delivery.
- **Subphase G: Receipts, typing and presence:** Delivery/read receipts, read cursors, ephemeral typing indicators with TTL, and presence tracking.
- **Subphase H: Attachments:** MIME and magic bytes validation, signed upload/download URLs, conversation authorization.
- **Subphase I: Group messaging:** Group creation, participant invitations, roles (admin/member), history, and revocation on member removal.
- **Subphase J: Marketplace integration:** Hook into mutual flatmate matches, property inquiries, rental applications, viewings, and lifecycle events.
- **Subphase K: Safety and moderation:** Block enforcement, spam rate limits, report message/conversation, suspicious link masking.
- **Subphase L: Notifications:** In-app notification dispatch over WebSocket, preferences, and email interface.
- **Subphase M: Frontend implementation:** Complete UI with inbox, conversation list, virtualized chat, attachment selector, typing, receipts, and responsive design.
- **Subphase N: Security and performance testing:** Unit, integration, security IDOR, concurrent load, and reconnect tests.
- **Subphase O: Staging deployment and browser E2E:** Verification in staging environment and complete documentation suite.
