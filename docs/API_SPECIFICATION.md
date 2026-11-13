# API Specification: Flatmate Compatibility & Rental Marketplace

**Base URI:** `/api/v1`  
**Protocol:** REST (HTTPS) + WebSockets (WSS)  
**Authentication:** Supabase Auth Bearer JWT Header (`Authorization: Bearer <token>`)  
**Standard Error Envelope:** RFC 7807 (Problem Details)  

---

## 1. Domain Module Endpoint Inventory

### 1.1 Identity & Authentication (`/api/v1/auth`)
- `POST /api/v1/auth/register` — Register user with initial role(s)
- `POST /api/v1/auth/login` — Authenticate user, return Supabase JWT access & refresh tokens
- `POST /api/v1/auth/refresh` — Refresh access token
- `POST /api/v1/auth/logout` — Terminate session
- `POST /api/v1/auth/otp/send` — Request mobile OTP verification (India-specific)
- `POST /api/v1/auth/otp/verify` — Verify mobile OTP

### 1.2 User Management (`/api/v1/users`)
- `GET /api/v1/users/me` — Current user profile and roles
- `PUT /api/v1/users/me` — Update user details
- `GET /api/v1/users/me/roles` — List user's assigned roles (tenant, owner, pg_operator, broker, etc.)
- `POST /api/v1/users/me/roles` — Add a new operational role to account

### 1.3 Profiles (`/api/v1/profiles`)
- `GET /api/v1/profiles/me` — User's personal, professional, and educational profile
- `PUT /api/v1/profiles/me` — Update personal profile details
- `PUT /api/v1/profiles/me/professional` — Update professional taxonomy (domain, designation, schedule)
- `PUT /api/v1/profiles/me/education` — Update university / college details
- `GET /api/v1/profiles/{user_id}` — View public seeker/host profile with privacy masking

### 1.4 Professional Taxonomy (`/api/v1/domains`)
- `GET /api/v1/domains/` — List configurable professional sectors & domains (Tech, Finance, Healthcare, Creative, Research, etc.)
- `GET /api/v1/domains/{domain_id}/professions` — List professions within domain

### 1.5 Lifestyle Questionnaire (`/api/v1/lifestyle`)
- `GET /api/v1/lifestyle/me` — Fetch 10-dimension questionnaire responses
- `PUT /api/v1/lifestyle/me` — Submit/update lifestyle preferences (sleep, cleanliness, noise, lighting, visitors, cooking, food)
- `GET /api/v1/lifestyle/dealbreakers` — User-configured mandatory dealbreakers

### 1.6 Properties & Configurations (`/api/v1/properties`)
- `GET /api/v1/properties/` — Search and filter properties (City, Locality, Configuration: 1RK, 1BHK, 2BHK, 3BHK, 4BHK+, PG)
- `POST /api/v1/properties/` — Register a new property listing (Owner / Authorized Tenant / Manager)
- `GET /api/v1/properties/{id}` — Retrieve detailed property information, room/unit breakdown
- `PUT /api/v1/properties/{id}` — Update property details
- `DELETE /api/v1/properties/{id}` — Deactivate or archive property listing

### 1.7 Rooms & Beds (`/api/v1/rooms`)
- `GET /api/v1/rooms/{id}` — Room specifications (private vs shared, attached bath, rent)
- `GET /api/v1/rooms/{id}/beds` — Bed-level availability and current occupancy status

### 1.8 PG Accommodation Management (`/api/v1/pg`)
- `GET /api/v1/pg/facilities` — List PG listings with meal arrangements, rules, and floor-wise availability
- `POST /api/v1/pg/buildings` — PG Operator building registration (floors, room layout, beds)

### 1.9 Search & Discovery (`/api/v1/search`)
- `POST /api/v1/search/properties` — PostGIS radius search, locality search, rent & configuration filters
- `POST /api/v1/search/flatmates` — PostGIS and lifestyle filtered seeker search

### 1.10 Compatibility & Recommendations (`/api/v1/matching`)
- `GET /api/v1/matching/recommendations` — Algorithmic top matches sorted by 10-factor weighted compatibility
- `GET /api/v1/matching/explain/{target_user_id}` — Transparent, explainable breakdown of alignment across all 10 axes
- `POST /api/v1/matching/interact` — Record match interaction (`like`, `pass`, `save`, `interest`)

### 1.11 Groups ("Team-Up to Rent") (`/api/v1/groups`)
- `GET /api/v1/groups/` — Explore open flatmate syndicates
- `POST /api/v1/groups/` — Create new group
- `POST /api/v1/groups/{id}/invite` — Send group membership invite
- `GET /api/v1/groups/{id}/compatibility` — Collective & pairwise conflict analysis for group members
- `POST /api/v1/groups/{id}/wishlist` — Add listing to group wishlist and cast vote

### 1.12 Applications & Enquiries (`/api/v1/applications`)
- `POST /api/v1/applications/` — Submit rental tenancy application
- `GET /api/v1/applications/me` — List applications submitted by user
- `PATCH /api/v1/applications/{id}/status` — Status state machine transition (`submitted` -> `reviewing` -> `accepted` / `rejected`)

### 1.13 Appointments & Viewings (`/api/v1/appointments`)
- `POST /api/v1/appointments/` — Schedule physical or virtual property viewing
- `PATCH /api/v1/appointments/{id}/reschedule` — Reschedule viewing appointment
- `PATCH /api/v1/appointments/{id}/cancel` — Cancel appointment

### 1.14 Messaging (`/api/v1/messages`)
- `GET /api/v1/messages/conversations` — User's active conversations
- `GET /api/v1/messages/conversations/{id}/messages` — Message history with pagination
- `POST /api/v1/messages/` — Send message with attachment/property card metadata

### 1.15 Notifications (`/api/v1/notifications`)
- `GET /api/v1/notifications/` — In-app notification feed
- `PATCH /api/v1/notifications/{id}/read` — Mark notification read

### 1.16 Trust, Verification & Moderation (`/api/v1/verification`, `/api/v1/moderation`)
- `POST /api/v1/verification/submit` — Submit identity/student/employment verification documents
- `GET /api/v1/verification/status` — Current trust score and badges
- `POST /api/v1/moderation/report` — Report listing, user, or message for policy violation

### 1.17 Administration (`/api/v1/admin`)
- `GET /api/v1/admin/moderation/queue` — Review flagged reports
- `PATCH /api/v1/admin/verifications/{id}` — Approve or reject user/property verification
- `GET /api/v1/admin/audit-logs` — Audit log of all privileged operations
