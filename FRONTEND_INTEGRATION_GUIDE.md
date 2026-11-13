# Frontend Integration Guide
## Flatmate Compatibility & Rental Marketplace

**Audience:** Frontend Engineers, Mobile Engineers, Fullstack Integrators  
**Backend API Version:** `v1`  
**Base URL:** `http://localhost:8000/api/v1` (Local) / `https://api.flatmate.internal/api/v1` (Production)  

---

## 1. Authentication & Session Management

All secured API endpoints require a standard HTTP Authorization header containing a Bearer JWT:
```http
Authorization: Bearer <access_token>
```

### 1.1 Auth Endpoints
- `POST /auth/register`: Create a new user account (supports roles: `seeker`, `owner`, `admin`, `pg_operator`).
- `POST /auth/login`: Authenticate and receive `access_token`, `refresh_token`, and user profile.
- `GET /auth/me`: Retrieve current user context and assigned roles.

---

## 2. Core API Integration Endpoints

### 2.1 Profiles & Lifestyle
- `GET /profiles/me`: Fetch current user's personal & professional profile.
- `PUT /profiles/me`: Update display name, occupation, company, bio, and privacy settings.
- `POST /lifestyle/quiz`: Submit 10-factor lifestyle questionnaire (sleep schedule, cleanliness, diet, smoking, etc.).
- `GET /lifestyle/dealbreakers`: Retrieve user-configured hard dealbreakers.

### 2.2 Property & Inventory
- `GET /properties`: List verified listings with filters (`city`, `locality`, `max_rent`, `furnishing`).
- `POST /properties`: Create property listing (Owners, Tenants, PG Operators).
- `GET /properties/{id}`: Detailed property view including room hierarchy, available beds, and amenities.
- `POST /properties/{id}/rooms`: Add bedroom inventory with individual bed occupancies.

### 2.3 Search & Geospatial Discovery
- `GET /search/properties`: Spatial proximity search (`lat`, `lng`, `radius_km`).
  > *Note:* Unauthenticated or unmatched seekers receive fuzzed coordinates (~1.1 km radius) to protect resident privacy.
- `GET /search/flatmates`: Search compatible flatmates by locality, profession, and budget.

### 2.4 Compatibility & Matching
- `POST /matching/calculate`: Evaluate explainable compatibility between two user IDs.
  - Returns: `overall_score` (0-100), `dealbreakers_cleared` (bool), `factors` breakdown, and `explanations`.
- `GET /matching/feed`: Fetch personalized recommendations ranked by lifestyle compatibility.
- `POST /matching/interact`: Record swipe/action (`like`, `pass`, `bookmark`). Mutual likes produce a match channel.

### 2.5 Groups & Collective Matching
- `POST /groups`: Create a new flatmate hunting group.
- `POST /groups/{id}/members`: Invite or add group members.
- `GET /groups/{id}/compatibility`: Evaluate collective pairwise compatibility ($C(n, 2)$) with conflict alerts.
- `POST /groups/{id}/wishlist`: Add property to shared group wishlist with member up/down voting.

### 2.6 Applications & Appointments
- `POST /applications`: Submit rental application for a property or specific room.
- `PATCH /applications/{id}/status`: Owner review (`under_review`, `accepted`, `rejected`).
- `POST /appointments`: Book viewing appointment (enforces 30-minute conflict window).

### 2.7 Messaging & Notifications
- `GET /messaging/conversations`: List active chat channels (direct, match, group, enquiry).
- `POST /messaging/conversations/{id}/messages`: Send message (scanned by heuristic scam & PII detector).
- `GET /notifications`: List in-app notifications (5-minute deduplication window).

---

## 3. RFC 7807 Error Response Handling

The backend returns standardized Problem Details format for all HTTP 4xx/5xx responses:

```json
{
  "type": "https://api.flatmate.internal/errors/conflict",
  "title": "Resource Conflict",
  "status": 409,
  "detail": "Viewing appointment overlaps with an existing confirmed booking within 30 minutes.",
  "instance": "/api/v1/appointments",
  "timestamp": "2026-11-13T12:00:00Z",
  "code": "APPOINTMENT_CONFLICT",
  "request_id": "req-8f4b2a"
}
```

---

## 4. Using the `@flatmate/contracts` Package

Frontend applications should consume TypeScript types directly from `@flatmate/contracts`:

```typescript
import { 
  UserDTO, 
  PropertyDTO, 
  ScoreBreakdown, 
  ApplicationDTO, 
  ConversationDTO 
} from "@flatmate/contracts";

import { apiClient } from "@/lib/api-client";

// Strongly-typed API request
const properties = await apiClient<PropertyDTO[]>("/properties", {
  params: { city: "Bengaluru", max_rent: "40000" }
});
```
