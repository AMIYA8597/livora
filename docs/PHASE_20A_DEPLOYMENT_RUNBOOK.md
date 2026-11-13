# PHASE 20A — REAL-TIME MESSAGING DEPLOYMENT RUNBOOK

**System:** Flatmate Compatibility & Rental Marketplace  
**Phase:** 20A — Real-Time Communication Engineering  
**Target:** Staging & Production Containerized Environments

---

## 1. Prerequisites & Environment Variables

Ensure the following environment variables are set in `.env` / deployment configuration:

```ini
# Database (PostgreSQL 16+)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/flatmate_db

# Security & Tokens
JWT_SECRET=your-secure-256bit-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Storage
STORAGE_TYPE=local # or "supabase"
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

# Redis Pub/Sub (Required for multi-replica horizontal clustering)
REDIS_URL=redis://localhost:6379

# WebSocket Endpoint
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/messaging/ws
```

---

## 2. Database Migration Steps

Execute Alembic migrations to apply Phase 20A schema enhancements:

```bash
# Navigate to API root
cd apps/api

# Run forward migrations
alembic upgrade head
```

Verify newly created tables and indexes:
```sql
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('conversations', 'conversation_participants', 'messages', 'attachments', 'conversation_read_cursors', 'conversation_preferences', 'outbox_events');
```

---

## 3. Verifying Health & Connectivity

1. **REST Health Check:**
   ```bash
   curl -i http://localhost:8000/api/v1/messaging/conversations -H "Authorization: Bearer <TOKEN>"
   ```
   Expected: `200 OK` with JSON array.

2. **WebSocket Handshake Check:**
   Connect via WebSocket client:
   `ws://localhost:8000/api/v1/messaging/ws?token=<TOKEN>`
   Expected immediate frame:
   ```json
   {
     "version": "1.0",
     "event": "connection.ready",
     "data": { "heartbeat_interval_ms": 30000, ... }
   }
   ```

3. **Multi-Instance Verification:**
   Launch two API instances behind load balancer. Verify message published by client on instance 1 is relayed to client on instance 2 via Redis channel `flatmate:chat:events`.
