# API & WebSocket Specification

**Base Path:** `/api/v1`  
**Protocol:** REST (HTTPS) + WebSockets (WSS)  
**Authentication:** HTTP Bearer Header (`Authorization: Bearer <jwt_access_token>`)  
**Standard Error Format:** RFC 7807 (Problem Details for HTTP APIs)  

---

## 1. Global Response Envelopes

### 1.1 Success Response Envelope
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully",
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 142
  }
}
```

### 1.2 Error Response Envelope
```json
{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Property with ID 4fae2e... was not found.",
    "details": []
  }
}
```

---

## 2. REST Endpoints by Domain Module

### 2.1 Authentication (`/auth`)
| Method | Path | Description | Access |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/register` | Register new user account with role | Public |
| `POST` | `/auth/login` | Email/password login, returns JWT access & refresh tokens | Public |
| `POST` | `/auth/refresh` | Exchange valid refresh token for a new access token | Public |
| `GET` | `/auth/me` | Fetch currently authenticated user identity | Authenticated |
| `POST` | `/auth/logout` | Revoke tokens & terminate session | Authenticated |

### 2.2 Profiles & Lifestyle Questionnaire (`/profiles`)
| Method | Path | Description | Access |
| :--- | :--- | :--- | :--- |
| `GET` | `/profiles/me` | Retrieve profile and lifestyle matrix for current user | Authenticated |
| `PUT` | `/profiles/me` | Update general profile details (bio, budget, move-in) | Authenticated |
| `POST`| `/profiles/me/quiz`| Submit completed lifestyle survey, updates vector embedding | Authenticated |
| `GET` | `/profiles/{id}`| View public seeker/host profile | Authenticated |

### 2.3 Properties & Rooms (`/properties`)
| Method | Path | Description | Access |
| :--- | :--- | :--- | :--- |
| `GET` | `/properties/` | List properties with filters (price, bedrooms, amenities) | Public |
| `GET` | `/properties/{id}`| Get comprehensive property details, room list, and host info | Public |
| `POST`| `/properties/` | Create a new property listing | Host / Owner |
| `PUT` | `/properties/{id}`| Update property listing details | Host / Owner |
| `DELETE`| `/properties/{id}`| Soft-delete or archive listing | Host / Owner |
| `POST`| `/properties/search/geo` | PostGIS spatial search by lat, lng & radius_km | Public |

### 2.4 Matching Engine (`/matching`)
| Method | Path | Description | Access |
| :--- | :--- | :--- | :--- |
| `GET` | `/matching/recommendations` | Get top ranked flatmate & room matches with score breakdown | Authenticated |
| `GET` | `/matching/compatibility/{target_id}` | Calculate direct compatibility score between current user and target seeker | Authenticated |

### 2.5 Flatmate Groups & Syndicates (`/groups`)
| Method | Path | Description | Access |
| :--- | :--- | :--- | :--- |
| `GET` | `/groups/` | List public flatmate groups seeking additional members | Authenticated |
| `POST`| `/groups/` | Create a new flatmate hunting group | Authenticated |
| `GET` | `/groups/{id}` | Retrieve group details, member roster, and shared wishlist | Authenticated |
| `POST`| `/groups/{id}/members/invite` | Invite a seeker to join the group | Group Admin |
| `POST`| `/groups/{id}/wishlist/{property_id}` | Add property to group wishlist and cast vote | Group Member |

### 2.6 Applications (`/applications`)
| Method | Path | Description | Access |
| :--- | :--- | :--- | :--- |
| `POST`| `/applications/` | Submit a rental application for a property/room | Seeker |
| `GET` | `/applications/me` | View applications submitted by current user | Seeker |
| `GET` | `/applications/{id}` | View full application details | Applicant / Owner |
| `PATCH`| `/applications/{id}/status` | Update application status (`reviewing`, `accepted`, `rejected`) | Property Owner |

### 2.7 Owners Dashboard (`/owners`)
| Method | Path | Description | Access |
| :--- | :--- | :--- | :--- |
| `GET` | `/owners/dashboard` | Aggregated statistics (views, inquiries, occupancy rate) | Host / Owner |
| `GET` | `/owners/listings` | List properties owned by the current user | Host / Owner |
| `GET` | `/owners/applications` | Review incoming applications across all managed properties | Host / Owner |

### 2.8 Verification & Trust (`/verification`)
| Method | Path | Description | Access |
| :--- | :--- | :--- | :--- |
| `POST`| `/verification/submit` | Upload ID, passport, or employment proof | Authenticated |
| `GET` | `/verification/status` | View current trust score and verified credential badges | Authenticated |

### 2.9 Moderation (`/moderation`)
| Method | Path | Description | Access |
| :--- | :--- | :--- | :--- |
| `POST`| `/moderation/report` | Submit an abuse/fraud report against a user or listing | Authenticated |
| `GET` | `/moderation/admin/reports` | List flagged reports queue | Admin |

---

## 3. Real-Time WebSocket Protocol

### 3.1 Connection Handshake
- **URL**: `ws://localhost:8000/api/v1/messaging/ws?token=<JWT_ACCESS_TOKEN>`
- **Authorization**: Token verified on handshake. Rejects connection with code `4401` if invalid or expired.

### 3.2 Protocol Events & Payloads

#### Client to Server: Send Message
```json
{
  "action": "send_message",
  "data": {
    "conversation_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "content": "Hi! When is the room available for viewing?",
    "message_type": "text"
  }
}
```

#### Server to Client: Broadcast Message
```json
{
  "event": "message_received",
  "data": {
    "id": "e0b57cf6-0ec8-45e6-9cf8-3a9a105f9920",
    "conversation_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "sender_id": "c1f24d77-628d-42ef-83e9-74d39a1391aa",
    "content": "Hi! When is the room available for viewing?",
    "message_type": "text",
    "sent_at": "2026-11-13T12:00:00Z"
  }
}
```

#### Client to Server: Typing Indicator
```json
{
  "action": "typing",
  "data": {
    "conversation_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "is_typing": true
  }
}
```
