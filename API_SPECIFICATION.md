# API Specification: Flatmate Compatibility & Rental Marketplace

**Base URI:** `/api/v1`  
**Staging Host:** `https://flatmate-api-staging-<hash>.a.run.app/api/v1` (Cloud Run)  
**Protocol:** REST (HTTPS) + WebSockets (WSS)  
**Authentication:** Supabase Auth Bearer JWT Header (`Authorization: Bearer <token>`)  
**Standard Error Envelope:** RFC 7807 (Problem Details - `application/problem+json`)  
**Total Endpoints:** 98 Endpoints across 20 Modules  
**Specification Version:** OpenAPI 3.1.0  
**Phase:** 20 Validated & Staging Deployed  

---

## 1. Domain Module Endpoint Inventory

### 1.1 Identity & Authentication (`/api/v1/auth`)
- `POST /api/v1/auth/register` — Register user with initial role(s)
- `POST /api/v1/auth/login` — Authenticate user, return Supabase JWT access & refresh tokens
- `POST /api/v1/auth/refresh` — Refresh access token
- `POST /api/v1/auth/logout` — Terminate session
- `POST /api/v1/auth/forgot-password` — Request password reset email
- `POST /api/v1/auth/reset-password` — Complete password reset with signed token
- `POST /api/v1/auth/otp/send` — Request mobile OTP verification (India-specific)
- `POST /api/v1/auth/otp/verify` — Verify mobile OTP

### 1.2 User Management (`/api/v1/users`)
- `GET /api/v1/users/me` — Current user profile and roles
- `PUT /api/v1/users/me` — Update user details
- `DELETE /api/v1/users/me` — Cascade delete user account (DPDP Act right to erasure)
- `GET /api/v1/users/me/roles` — List user's assigned roles (seeker, owner, pg_operator, broker, etc.)
- `POST /api/v1/users/me/roles` — Add a new operational role to account

### 1.3 Profiles & Lifestyle (`/api/v1/profiles` & `/api/v1/lifestyle`)
- `GET /api/v1/profiles/me` — User's personal, professional, and educational profile
- `PUT /api/v1/profiles/me` — Update personal profile details
- `GET /api/v1/profiles/{id}` — Retrieve candidate profile (respecting privacy settings)
- `GET /api/v1/lifestyle/` — Retrieve current user's lifestyle habits
- `POST /api/v1/lifestyle/` — Save or update 10-dimension questionnaire
- `GET /api/v1/lifestyle/{user_id}` — Retrieve lifestyle survey (enforces `matched_only` privacy check)

### 1.4 Properties & Inventory (`/api/v1/properties`)
- `GET /api/v1/properties/` — Search listings with PostGIS spatial radius and price filters
- `POST /api/v1/properties/` — Create new property listing with rooms and beds
- `GET /api/v1/properties/{id}` — Retrieve listing details (coordinates fuzzed to 2 decimals for public)
- `PUT /api/v1/properties/{id}` — Update property (enforces BOLA owner check)
- `DELETE /api/v1/properties/{id}` — Delete property (enforces BOLA owner check)
- `GET /api/v1/properties/{id}/inventory` — Retrieve room and bed real-time occupancy status

### 1.5 Matching & Compatibility (`/api/v1/matching`)
- `GET /api/v1/matching/recommendations` — Fetch AI-assisted roommate recommendations (excludes blocked users)
- `POST /api/v1/matching/interactions` — Record like, pass, or match interaction
- `GET /api/v1/matching/compatibility/{target_user_id}` — Get 10-dimension score breakdown

### 1.6 Applications (`/api/v1/applications`)
- `POST /api/v1/applications/` — Submit rental application for property/room/bed
- `GET /api/v1/applications/` — List applications (filtered by applicant or owner)
- `GET /api/v1/applications/{id}` — Get application details
- `PATCH /api/v1/applications/{id}/status` — Advance application state (enforces BOLA & state machine)

### 1.7 Real-Time Messaging (`/api/v1/messages` & WebSocket)
- `GET /api/v1/messages/conversations` — List user's active conversations
- `POST /api/v1/messages/conversations` — Create direct or group conversation
- `GET /api/v1/messages/{conversation_id}` — Paginate chat messages
- `POST /api/v1/messages/` — Send transactional message
- `POST /api/v1/messages/{conversation_id}/read` — Update read cursor
- `WS /api/v1/messaging/ws` — Real-time bidirectional WebSocket chat stream

### 1.8 Moderation & Safety (`/api/v1/moderation`)
- `POST /api/v1/moderation/reports` — Report abusive behavior or fraudulent listing
- `POST /api/v1/moderation/blocks` — Block user (enforces bidirectional isolation)
- `GET /api/v1/moderation/reports` — Admin moderation queue review
- `PATCH /api/v1/moderation/reports/{id}` — Resolve or escalate report

---

## 2. Standard Error Response Contract (RFC 7807)

```json
{
  "type": "https://errors.flatmate.platform/forbidden",
  "title": "Forbidden",
  "status": 403,
  "detail": "You do not have permission to modify this property.",
  "instance": "/api/v1/properties/084d5df3-9e48-43d9-a0a1-9da0e90eb857",
  "request_id": "99351e1d-dcf4-49c0-be87-e23a49e6d0a7"
}
```
