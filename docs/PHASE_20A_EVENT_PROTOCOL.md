# PHASE 20A — REAL-TIME MESSAGING EVENT PROTOCOL SPECIFICATION

**Protocol Version:** `v1`  
**Transport:** WebSocket (`ws://` / `wss://`) & Distributed Pub/Sub  
**Standard Envelope:** JSON format with version, event type, timestamp, sequence/correlation ID, and typed payload.

---

## 1. Frame Envelope Structure

All client-to-server and server-to-client WebSocket messages adhere to the standard `v1` envelope:

```json
{
  "version": "1.0",
  "event": "<event_name>",
  "timestamp": "2026-11-13T20:00:00.000Z",
  "correlation_id": "optional-uuid-for-request-matching",
  "data": { ... }
}
```

---

## 2. Event Catalog & Payload Specifications

### 2.1 Connection Lifecycle

#### `connection.ready` (Server -> Client)
Sent immediately after successful WebSocket handshake and JWT verification.
```json
{
  "version": "1.0",
  "event": "connection.ready",
  "timestamp": "2026-11-13T20:00:01.000Z",
  "data": {
    "user_id": "84c8a2ef-9cb8-4a52-b91c-bf530f8826c7",
    "session_id": "ws-sess-001a",
    "heartbeat_interval_ms": 30000,
    "server_time": "2026-11-13T20:00:01.000Z"
  }
}
```

#### `ping` / `pong` (Bidirectional)
Keep-alive heartbeat frames.
- Client -> Server: `{"version": "1.0", "event": "ping"}`
- Server -> Client: `{"version": "1.0", "event": "pong"}`

---

### 2.2 Messaging Events

#### `message.send` (Client -> Server)
Client submits a new message via WebSocket.
```json
{
  "version": "1.0",
  "event": "message.send",
  "correlation_id": "f5e4c3b2-a109-4876-b543-210fedcba987",
  "data": {
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "content": "Hi, is the flat still available for move-in next month?",
    "message_type": "text",
    "idempotency_key": "c8d7e6f5-b4a3-4921-9876-123456abcdef",
    "reply_to_message_id": null,
    "attachment_ids": []
  }
}
```

#### `message.created` (Server -> Broadcast to Conversation Members)
Emitted when a message has been safely committed to PostgreSQL.
```json
{
  "version": "1.0",
  "event": "message.created",
  "correlation_id": "f5e4c3b2-a109-4876-b543-210fedcba987",
  "data": {
    "id": "11111111-2222-3333-4444-555555555555",
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "sender_id": "84c8a2ef-9cb8-4a52-b91c-bf530f8826c7",
    "content": "Hi, is the flat still available for move-in next month?",
    "message_type": "text",
    "idempotency_key": "c8d7e6f5-b4a3-4921-9876-123456abcdef",
    "reply_to_message_id": null,
    "attachments": [],
    "sent_at": "2026-11-13T20:00:02.123Z",
    "status": "sent"
  }
}
```

#### `message.updated` (Server -> Broadcast)
Emitted when a message is edited by its author.
```json
{
  "version": "1.0",
  "event": "message.updated",
  "data": {
    "id": "11111111-2222-3333-4444-555555555555",
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "content": "Hi, is the master room available for move-in next month?",
    "is_edited": true,
    "edited_at": "2026-11-13T20:02:10.000Z"
  }
}
```

#### `message.deleted` (Server -> Broadcast)
Emitted when a message is soft-deleted by its author or moderator.
```json
{
  "version": "1.0",
  "event": "message.deleted",
  "data": {
    "id": "11111111-2222-3333-4444-555555555555",
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "is_deleted": true,
    "deleted_at": "2026-11-13T20:05:00.000Z"
  }
}
```

---

### 2.3 Delivery & Read Receipts

#### `message.delivered` (Server -> Broadcast to Conversation Members)
Emitted when a message is delivered to a participant's device or active session.
```json
{
  "version": "1.0",
  "event": "message.delivered",
  "data": {
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "message_id": "11111111-2222-3333-4444-555555555555",
    "user_id": "99999999-8888-7777-6666-555555555555",
    "delivered_at": "2026-11-13T20:00:03.000Z"
  }
}
```

#### `message.read` (Bidirectional)
- Client -> Server: Client informs server that a conversation has been read up to a message cursor.
- Server -> Broadcast: Notifies other members of the updated read cursor.
```json
{
  "version": "1.0",
  "event": "message.read",
  "data": {
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "last_read_message_id": "11111111-2222-3333-4444-555555555555",
    "user_id": "99999999-8888-7777-6666-555555555555",
    "read_at": "2026-11-13T20:00:05.000Z"
  }
}
```

---

### 2.4 Ephemeral Typing & Presence

#### `typing.started` & `typing.stopped` (Bidirectional)
Typing states are ephemeral and automatically expire after 5 seconds if no renew is received.
```json
{
  "version": "1.0",
  "event": "typing.started",
  "data": {
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "user_id": "84c8a2ef-9cb8-4a52-b91c-bf530f8826c7"
  }
}
```

#### `presence.changed` (Server -> Broadcast)
Emitted to contacts/conversations when a user comes online or goes offline.
```json
{
  "version": "1.0",
  "event": "presence.changed",
  "data": {
    "user_id": "84c8a2ef-9cb8-4a52-b91c-bf530f8826c7",
    "status": "online",
    "last_seen_at": "2026-11-13T20:00:00.000Z"
  }
}
```

---

### 2.5 Conversation & Group Management Events

#### `conversation.updated` (Server -> Broadcast)
Emitted when conversation metadata, title, or pinned attributes change.
```json
{
  "version": "1.0",
  "event": "conversation.updated",
  "data": {
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "Indiranagar 3BHK Flat Hunt",
    "last_message_at": "2026-11-13T20:00:02.123Z"
  }
}
```

#### `conversation.member_added` (Server -> Broadcast)
Emitted when a new member joins or is invited to a group conversation.
```json
{
  "version": "1.0",
  "event": "conversation.member_added",
  "data": {
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "user_id": "77777777-6666-5555-4444-333333333333",
    "role": "member",
    "joined_at": "2026-11-13T20:10:00.000Z"
  }
}
```

#### `conversation.member_removed` (Server -> Broadcast)
Emitted when a member leaves or is removed by a group admin.
```json
{
  "version": "1.0",
  "event": "conversation.member_removed",
  "data": {
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "user_id": "77777777-6666-5555-4444-333333333333",
    "removed_at": "2026-11-13T20:12:00.000Z"
  }
}
```

---

### 2.6 Real-Time In-App Notifications

#### `notification.created` (Server -> Recipient Client)
Emitted directly to a user's WebSocket connection when an in-app notification is dispatched.
```json
{
  "version": "1.0",
  "event": "notification.created",
  "data": {
    "id": "55555555-4444-3333-2222-111111111111",
    "title": "New Viewing Request",
    "body": "Amit requested a viewing for Koramangala 2BHK on Saturday.",
    "notification_type": "viewing_reminder",
    "reference_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "created_at": "2026-11-13T20:15:00.000Z"
  }
}
```

---

### 2.7 Error Envelopes

#### `error` (Server -> Client)
Emitted when an action is rejected or invalid.
```json
{
  "version": "1.0",
  "event": "error",
  "correlation_id": "f5e4c3b2-a109-4876-b543-210fedcba987",
  "data": {
    "code": "FORBIDDEN",
    "message": "You cannot message this user because they have blocked you."
  }
}
```
