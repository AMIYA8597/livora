# PHASE 20A — REAL-TIME MESSAGING FRONTEND INTEGRATION GUIDE

**System:** Flatmate Compatibility & Rental Marketplace  
**Framework:** Next.js 14 (App Router) + React 18 + Tailwind CSS  
**Package:** `@flatmate/contracts` + `@flatmate/ui`

---

## 1. Overview & Components

The Phase 20A frontend messaging interface comprises:
1. **Inbox Page (`apps/web/app/messages/page.tsx`):**
   - Full-page responsive messaging layout.
   - Conversation sidebar with category tabs (`All`, `Direct`, `Properties`, `Groups`, `Archived`).
   - Real-time search query filtering over titles and recent message snippets.
   - Live presence indicator on participant avatars.
   - Unread message counters per conversation and dynamic total badges.
   - Participant & conversation details slide-out drawer.
2. **Interactive Chat Window (`apps/web/features/messaging/components/ChatWindow.tsx`):**
   - Chronological message stream with sender avatars and timestamps.
   - Self vs. peer message bubble styling.
   - Read receipt indicators:
     - 🕒 `sending`: message queued / in flight
     - ✓ `sent`: committed to server
     - ✓✓ `delivered`: delivered to peer socket
     - ✓✓ (Blue): `read`: viewed by peer
   - Ephemeral typing indicators (`Priya is typing...`).
   - Reply-to preview bubble and quote references.
   - Secure file attachment picker supporting JPEG, PNG, WebP, and PDF (up to 10MB).
   - In-flight safety banners detecting rental advance scams and unverified phone exchanges.
   - Message action menus: Reply, Edit, Delete.
3. **Resilient WebSocket Hook (`apps/web/hooks/useSocket.ts`):**
   - Authenticated WebSocket client using bearer JWT.
   - Exponential backoff reconnection with jitter (1s - 15s).
   - Automated 25s ping/pong keep-alive heartbeat.
   - Strongly-typed `v1` event protocol dispatching.

---

## 2. Shared Types & Contracts

Import from `@flatmate/contracts`:
```typescript
import {
  ConversationDTO,
  MessageDTO,
  AttachmentDTO,
  ConversationParticipantDTO,
  WebSocketEnvelope,
  SendMessageInput
} from '@flatmate/contracts';
```

---

## 3. Hook Usage Example

```typescript
import { useSocket } from "@/hooks/useSocket";

export function ChatContainer({ conversationId }: { conversationId: string }) {
  const { isConnected, startTyping, stopTyping, markRead } = useSocket({
    onMessageCreated: (msg) => {
      console.log("New message received:", msg);
    },
    onTypingStarted: ({ conversation_id, user_id }) => {
      console.log(`User ${user_id} is typing in ${conversation_id}`);
    },
    onMessageRead: ({ conversation_id, user_id, last_read_message_id }) => {
      console.log(`User ${user_id} read up to ${last_read_message_id}`);
    },
  });

  return (
    <div>
      <p>Status: {isConnected ? "Online" : "Reconnecting..."}</p>
    </div>
  );
}
```
