# PHASE 20A — REAL-TIME MESSAGING SECURITY ASSESSMENT

**Date:** November 2026  
**System:** Flatmate Compatibility & Rental Marketplace  
**Scope:** Security posture, vulnerability analysis, authorization boundaries, IDOR prevention, and penetration testing verification for the Phase 20A messaging subsystem.

---

## 1. Threat Modeling & Vulnerability Analysis

| Threat / Attack Vector | Vulnerability Addressed | Mitigation Mechanism | Verification Test |
| :--- | :--- | :--- | :--- |
| **Unauthenticated WebSocket Connection** | Attacker opens WebSocket stream without authentication credentials. | WebSocket connection rejects handshake with `WS_1008_POLICY_VIOLATION` if token is missing, expired, or invalid. | Verified in `websocket_endpoint` auth check. |
| **Expired or Tampered JWT** | Attacker uses forged signature or expired token claim. | Server decodes JWT via HMAC-SHA256 (`decode_token`); rejects tampered signatures or expired tokens. | Tested via `decode_token` validation. |
| **Forged Sender ID (Impersonation)** | Attacker injects a third party's `sender_id` into a message body or WS frame. | Server strictly derives `sender_id` from the verified JWT `sub` claim. Frontend-supplied sender IDs are completely discarded. | Tested in `send_message` and WS router. |
| **Conversation IDOR (Unauthorized Read)** | Non-participant attempts to query `/messaging/conversations/{id}/messages`. | Database query explicitly enforces active participant membership check (`is_active = True`). Raises `403 Forbidden` if user is not in conversation. | `test_messaging_participant_authorization_get_messages` |
| **Unauthorized Message Send** | Non-participant or expelled member posts to conversation. | Service checks `ConversationParticipant` for active membership prior to persisting message. | `test_messaging_participant_authorization_send_message` |
| **Attachment IDOR (Private Download)** | Attacker requests presigned URL for private attachment in another user's conversation. | Download route (`GET /messaging/attachments/{id}/download`) joins `attachments` with `conversation_participants` for caller. Non-members receive `403 Forbidden`. | Verified in `download_attachment` route. |
| **Block Bypass** | Blocked user attempts to message blocker or create new thread. | `MessagingService` queries `UserBlock` bidirectional table before conversation creation or message persistence. Raises `403 Forbidden`. | `test_blocked_user_cannot_initiate_conversation`, `test_blocked_user_cannot_send_message` |
| **Group Privilege Escalation** | Regular group member attempts to remove other participants or delete messages. | Administrative actions verify caller has `role == "admin"` in `conversation_participants`. | `test_group_participant_management_and_access_revocation` |
| **Removed Member Access Leak** | Removed member attempts to listen or send after removal. | `is_active` is set to `False`; future send/read checks immediately reject caller; WS events are excluded from departed members. | `test_group_participant_management_and_access_revocation` |
| **Malicious File Upload / Code Execution** | Attacker uploads executable binary renamed to `.jpg` or `.png`. | Storage service validates file size, checks magic byte signatures (`MAGIC_SIGNATURES`), executes malware scanner (`DefaultMalwareScanner`), and sanitizes extensions. | `test_storage_upload.py` |
| **Rental Advance Scam / Phishing** | Scam operators soliciting advance rent or deposit prior to property viewings. | Automated regex heuristic detects advance payment solicitations prior to physical inspection and flags warning banners. | `test_messaging.test.ts` |

---

## 2. Server-Side Authorization Boundary Checks

Every entry point to the messaging subsystem validates authorization strictly on the server:
- `GET /api/v1/messaging/conversations`: scoped to `current_user.id` via `ConversationParticipant.user_id`.
- `GET /api/v1/messaging/conversations/{id}`: validates caller is active participant.
- `GET /api/v1/messaging/conversations/{id}/messages`: validates caller is active participant.
- `POST /api/v1/messaging/messages`: validates caller is active participant and not blocked.
- `PATCH /api/v1/messaging/messages/{id}`: validates caller is the author of the message.
- `DELETE /api/v1/messaging/messages/{id}`: validates caller is author or group admin.
- `POST /api/v1/messaging/conversations/{id}/attachments`: validates caller is active participant.
- `GET /api/v1/messaging/attachments/{id}/download`: validates caller is active participant.

---

## 3. Defense-in-Depth & Privacy Safeguards

1. **Private Identity & Document Buckets:** Chat attachments and verification documents are stored in private storage buckets. Public access is disabled; all downloads require short-lived (1-hour) HMAC-signed presigned URLs.
2. **Ephemeral Presence & Typing Indicators:** Typing state is held in-memory with automatic 5-second TTL cancellation. No permanent disk footprint is stored for typing indicators.
3. **Audit History & Soft-Deletion:** Deleted messages retain author audit trails with content replaced by `"This message was deleted."` to prevent unmoderated abuse while respecting participant privacy.
