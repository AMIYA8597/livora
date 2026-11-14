# PHASE 21.2 — Multi-Environment Separation Guide

**Document Version:** 1.0  
**Phase:** 21.2 — Environment Separation & Isolation Standards  
**Date:** November 14, 2026  
**Auditor Roles:** Principal DevOps Engineer, Cloud Architect, Application Security Engineer  

---

## 1. Environment Separation Principles

To prevent data contamination, accidental external actions (e.g. sending real emails or SMS, triggering payment gateways), or security compromise:
1. **Database Isolation:** Staging environments connect exclusively to dedicated staging databases. Staging NEVER connects to production databases or shares database instances with production workloads.
2. **Credential Isolation:** Service role keys, JWT secrets, database credentials, and API tokens are distinct per environment. Staging uses dedicated staging service keys.
3. **URL and Routing Parity:** Frontend and backend staging URLs are strictly paired:
   - Cloud Staging: Frontend `https://staging.flatmate.platform` <-> Backend `https://api-staging.flatmate.platform/api/v1` <-> WebSockets `wss://api-staging.flatmate.platform/api/v1/messaging/ws`.
   - Local Isolated Staging: Frontend `http://localhost:3001` <-> Backend `http://localhost:8001/api/v1` <-> WebSockets `ws://localhost:8001/api/v1/messaging/ws`.
4. **Storage Bucket Isolation:** Staging storage buckets (`flatmate-media-staging`, `staging-property-photos`, `staging-verification-docs`) are isolated from production storage.
5. **Communication Sinks:** Email delivery and outbound SMS/notifications are routed to in-memory test sinks or sandbox SMTP capture (Mailpit/MailHog). Real customer emails are never dispatched.
6. **Zero Client-Side Secret Leakage:** `NEXT_PUBLIC_*` variables are strictly limited to non-sensitive identifiers (API URL, public anon key, app URL). Secret keys and service roles remain server-side only.

---

## 2. Environment Configuration Matrix

| Configuration Parameter | Local Development (`.env.example`) | Automated Testing (`apps/api/tests/`) | Staging (`.env.staging.example`) | Production (`.env.production.example`) |
| :--- | :--- | :--- | :--- | :--- |
| **`ENVIRONMENT`** | `development` | `test` | `staging` | `production` |
| **`DEBUG`** | `True` | `False` | `False` | `False` |
| **`LOG_LEVEL`** | `DEBUG` / `INFO` | `WARNING` | `INFO` | `WARNING` |
| **`DATABASE_URL`** | `localhost:5432/flatmate_db` | In-memory / ephemeral test DB | `staging-db:5432/postgres` (dedicated) | `prod-pooler:6543/postgres` (HA pooler) |
| **`SUPABASE_URL`** | `http://localhost:54321` | Mock client / local | `https://staging-project-ref.supabase.co` | `https://prod-project-ref.supabase.co` |
| **`STORAGE_BUCKET`**| `flatmate-media` | Mock / temporary dir | `flatmate-media-staging` | `flatmate-media` (production bucket) |
| **`REDIS_URL`** | `redis://localhost:6379/0` | In-memory / fallback | `rediss://...staging-redis...` | `rediss://...prod-redis...` |
| **`EMAIL_PROVIDER`**| `smtp` (port 1025) | `test-sink` (mock) | `test-sink` / sandbox | `resend` / AWS SES (verified domain) |
| **`CORS_ORIGINS`** | `localhost:3000` | Any | `staging.flatmate.platform` | `flatmate.platform` |
| **`X-Robots-Tag`** | `noindex, nofollow` | `noindex, nofollow` | `noindex, nofollow` | `all` (indexable) |

---

## 3. Deployment Checklist for Staging Isolation

- [x] `.gitignore` verified to exclude all `.env` and `.env.*` files containing secrets.
- [x] Only `.env.example`, `.env.staging.example`, and `.env.production.example` tracked in repository.
- [x] `NEXT_PUBLIC_*` variables audited: zero service-role keys, database passwords, or JWT secrets exposed.
- [x] Staging database connection string contains explicit `ssl=require` and points to staging host.
- [x] Staging email provider set to `test-sink` with `MOCK_EMAIL_DELIVERY=True`.
- [x] Storage buckets for staging prefixed with `staging-` to prevent bucket collisions.
- [x] CORS allowed origins configured to allow staging frontend while denying unauthorized origins.
