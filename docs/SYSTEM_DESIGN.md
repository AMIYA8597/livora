# System Architecture & Design Specification

**Document Version:** 1.0.0  
**Target Architecture:** Modular Monolith with Asynchronous Distributed Workers  

---

## 1. Architectural Philosophy

The **Flatmate Platform** utilizes a **Modular Monolith** architecture for the API backend paired with a **Server-Side Rendered (SSR) / Static Next.js 14 Frontend**.

### Why Modular Monolith?
- **High Cohesion, Low Coupling**: Modules (Auth, Profiles, Properties, Matching, Messaging) maintain strictly defined domain boundaries and communicate via explicit internal interfaces.
- **Operational Simplicity**: Avoids premature microservice distributed transaction overhead and networking latency.
- **Future-Proof**: Each module can be broken out into an independent microservice when scaling requirements dictate.

---

## 2. High-Level System Architecture

```mermaid
flowchart TB
    subgraph Clients["Client Tier"]
        WebBrowser["Modern Web Browsers (Next.js 14 SSR/SPA)"]
        MobilePWA["Mobile Responsive PWA"]
    end

    subgraph Edge["Edge & Load Balancing"]
        Nginx["Nginx Reverse Proxy / Cloudflare"]
    end

    subgraph AppTier["Application Tier"]
        FastAPI["FastAPI Modular Monolith Engine\n(Python 3.11+ / AsyncIO)"]
        WSServer["WebSocket Connection Gateway\n(FastAPI + Redis Pub/Sub)"]
    end

    subgraph Workers["Async Processing Tier"]
        CeleryWorker["Celery Worker Fleet"]
        CeleryBeat["Celery Beat Periodic Scheduler"]
    end

    subgraph DataTier["Data & Persistence Tier"]
        Postgres[("PostgreSQL 16\n- PostGIS (Geo Radius)\n- pgvector (Cosine Matches)\n- Row Level Security")]
        RedisCache[("Redis 7.2\n- Session Cache\n- Pub/Sub Messaging\n- Celery Broker / Results")]
        MinIOStorage[("MinIO / AWS S3\nEncrypted Media & Document Store")]
    end

    Clients --> Edge
    Edge --> WebBrowser
    Edge --> FastAPI
    Edge --> WSServer

    FastAPI --> Postgres
    FastAPI --> RedisCache
    FastAPI --> MinIOStorage
    FastAPI --> CeleryWorker

    WSServer <--> RedisCache

    CeleryWorker --> Postgres
    CeleryWorker --> RedisCache
    CeleryWorker --> MinIOStorage
    CeleryBeat --> CeleryWorker
```

---

## 3. Core Component Breakdown

### 3.1 Backend Application Core (`apps/api`)
Built with **FastAPI** leveraging `asyncio` for non-blocking I/O operations.
- **Core Layer**: Central configuration, async database session pooling (`asyncpg`), JWT authentication, exception handling, custom response envelopes.
- **Domain Modules**:
  1. `auth`: JWT issuance, OAuth2 token validation, password hashing via `passlib[bcrypt]`.
  2. `users`: User entity state, RBAC (Seeker, Owner, Admin).
  3. `profiles`: Questionnaire data, preferences, lifestyle attributes.
  4. `properties`: Listings, spatial geometries, room specifications, amenities.
  5. `matching`: Composite scoring algorithm & vector cosine similarity.
  6. `groups`: Hunting syndicates, collective wishlists, group voting.
  7. `applications`: Tenancy workflow state machine (Submitted -> Under Review -> Accepted / Declined).
  8. `owners`: Landlord dashboard, applicant screening, tenancy approval.
  9. `messaging`: Real-time conversation threads, read markers, attachments.
  10. `notifications`: Email, SMS, in-app notification dispatch.
  11. `verification`: Document upload, verification workflow, trust score aggregation.
  12. `moderation`: Report auditing, spam suppression, administrative control.

### 3.2 Matching Engine Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor Seeker as User (Seeker)
    participant API as Matching Module
    participant VectorDB as Postgres (pgvector)
    participant PostGIS as Postgres (PostGIS)
    participant Redis as Redis Cache

    Seeker->>API: GET /api/v1/matching/recommendations?radius_km=15
    API->>Redis: Check Cache: match_feed:{user_id}
    alt Cache Hit
        Redis-->>API: Return cached candidate IDs & scores
    else Cache Miss
        API->>PostGIS: Query listings within 15km of target coordinates
        PostGIS-->>API: Return candidate listings & hosts
        API->>VectorDB: Query cosine distance <=> user_lifestyle_vector
        VectorDB-->>API: Return ranked vector similarities
        API->>API: Execute Dealbreaker Rules & Weighted Composite Function
        API->>Redis: Set Cache (TTL = 15 mins)
    end
    API-->>Seeker: Paginated Matches with Compatibility Breakdown
```

### 3.3 Real-Time WebSocket Architecture

```mermaid
sequenceDiagram
    autonumber
    actor Alice as User A
    actor Bob as User B
    participant Node1 as FastAPI Instance 1
    participant Node2 as FastAPI Instance 2
    participant RedisPubSub as Redis Pub/Sub
    participant DB as Postgres

    Alice->>Node1: Connect WS /ws?token=JWT
    Bob->>Node2: Connect WS /ws?token=JWT
    Alice->>Node1: Send Message {recipient_id: Bob, text: "Hey! Loved your profile"}
    Node1->>DB: Persist Message (id, sender, recipient, timestamp)
    Node1->>RedisPubSub: PUBLISH channel:user_Bob payload
    RedisPubSub->>Node2: Distribute to subscribed worker
    Node2->>Bob: Deliver WebSocket Frame {event: "new_message", data: ...}
    Bob->>Node2: Send {event: "read_receipt", message_id: ...}
    Node2->>RedisPubSub: PUBLISH channel:user_Alice payload
    RedisPubSub->>Node1: Distribute
    Node1->>Alice: Deliver {event: "message_read", message_id: ...}
```

---

## 4. Data Storage Architecture

### 4.1 Relational Database (`PostgreSQL 16`)
- **Spatial Features (`PostGIS`)**:
  - `ST_DWithin` used for fast spatial bounding box and circular radius searches for listings and commute zones.
  - Spatial indexes (`GIST`) on `geometry(Point, 4326)`.
- **Vector Search (`pgvector`)**:
  - 64-dimensional lifestyle preference vectors.
  - `HNSW` (Hierarchical Navigable Small World) index with cosine distance operator `<=>` for sub-5ms neighbor searches across millions of profiles.

### 4.2 Cache & In-Memory State (`Redis 7.2`)
- **Key-Value Cache**: Profile summaries, frequently queried property listings, location geocoding lookup tables.
- **Ephemeral State**: Online presence tracking (`user:{id}:online`), typing indicators (3-second TTL keys).
- **Pub/Sub Channels**: Scalable inter-process event distribution for WebSocket cluster nodes.

### 4.3 Object Storage (`MinIO / S3`)
- Buckets:
  - `flatmate-public-photos`: Profile avatars, listing image galleries, group photos (CDN cached).
  - `flatmate-private-docs`: Identity documents, proof of employment/student status, rental references (AES-256 encrypted, presigned URLs only).

---

## 5. Scalability & Resilience

1. **Horizontal Scaling**:
   - FastAPI backend instances are stateless and run behind load balancers with sticky sessions disabled.
   - Database read replicas for search queries; master instance for write transactions.
2. **Rate Limiting**:
   - Token bucket algorithm implemented via Redis middleware protecting auth and messaging endpoints.
3. **Graceful Degradation**:
   - In case of vector index maintenance, matching falls back to heuristic category weights without breaking the API contract.
