# Frontend Integration Guide
## Flatmate Compatibility & Rental Marketplace

**Audience:** Frontend Engineers, Mobile Engineers, Fullstack Integrators  
**Backend API Version:** `v1` (110 Endpoints Registered)  
**Base URL:** `http://localhost:8000/api/v1` (Local) / `https://api-staging.flatmate.platform/api/v1` (Staging)  
**WebSocket URL:** `ws://localhost:8000/api/v1/messaging/ws` (Local) / `wss://api-staging.flatmate.platform/api/v1/messaging/ws` (Staging)  
**Frontend Framework:** Next.js 14.2.4 App Router (32 Production Routes)  
**Auth Strategy:** Supabase SSR with Asymmetric ES256 JWKS and Cookie Session Refresh  
**Phase:** Phase 23 — Real Hosted Database Integration & Full-Stack Validation  

---

## 1. Quick Start & Environment Configuration

### 1.1 Environment Variables
Create or verify `.env.local` inside `apps/web`:

```bash
# apps/web/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/messaging/ws
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
```

> [!CAUTION]
> Never put `SUPABASE_SERVICE_ROLE_KEY` or database connection strings in `apps/web/.env.local`. Client bundles are strictly audited (`security_auth.test.ts`) to prevent credential leakage.

---

## 2. Centralized API Client Architecture

All network communication is orchestrated through `apps/web/lib/api-client.ts`:

```typescript
import { apiClient, ApiError } from "@/lib/api-client";
import type { PropertyDTO } from "@flatmate/contracts";

// Type-safe GET request
try {
  const property = await apiClient.get<PropertyDTO>(`/properties/${propertyId}`);
  console.log("Property loaded:", property.title);
} catch (error) {
  if (error instanceof ApiError) {
    console.error(`API Error [${error.errorCode}]:`, error.detail);
    if (error.status === 403) {
      // Handle forbidden access
    }
  }
}
```

### Key Client Features:
- **Automatic JWT Bearer Token Injection:** Retrieves token from local storage and injects `Authorization: Bearer <token>`.
- **Transparent 401 Refresh Handling:** Intercepts 401 responses, initiates a single token refresh request, and retries pending requests.
- **RFC 7807 Problem Details Parsing:** Automatically extracts `errorCode`, `title`, `detail`, `invalidParams`, and `requestId`.
- **Timeout & Cancellation:** Built-in `AbortController` support with default 15-second timeouts.

---

## 3. Real-Time WebSocket Messaging Integration

```typescript
// Connect to real-time chat stream
const token = localStorage.getItem("access_token");
const ws = new WebSocket(`${process.env.NEXT_PUBLIC_WS_URL}?token=${token}`);

ws.onopen = () => {
  console.log("WebSocket connected to messaging stream");
};

ws.onmessage = (event) => {
  const payload = JSON.parse(event.data);
  switch (payload.event) {
    case "new_message":
      appendMessageToChat(payload.data);
      break;
    case "read_receipt":
      updateMessageStatus(payload.data.message_id, "read");
      break;
  }
};

ws.onclose = () => {
  // Implement exponential backoff with jitter
  setTimeout(reconnectWebSocket, Math.min(1000 * Math.pow(2, retryCount), 30000));
};
```

---

## 4. Currency & Formatting Guidelines

Always use the standardized utility functions from `@flatmate/contracts`:
- `formatCurrency(amount)`: Formats numbers into Indian Rupee strings (`₹45,000`).
- `formatIndianCompactCurrency(amount)`: Handles Lakhs and Crores (`₹4.5 L`, `₹1.2 Cr`).
- `formatDateTimeIST(isoString)`: Displays timestamps in Indian Standard Time (`DD MMM YYYY, hh:mm A IST`).
- `formatIndianPhoneNumber(phone)`: Masks and formats phone numbers (`+91 98**** *123`).
