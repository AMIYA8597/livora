# Phase 20 Secret Management & Cryptographic Security Architecture

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** Application Security Engineer & DevOps Engineer  

---

## 1. Secret Management Policy & Governance

In compliance with enterprise security requirements and mandatory Phase 20 operating principles:
- **Zero Credentials in Git:** Neither `.env`, `.env.staging`, nor `.env.production` files containing live secrets are ever committed to version control. All `.env*` files are strictly ignored via root `.gitignore`.
- **Reference Templates Provided:** Clean, documented templates with self-explanatory placeholders are maintained:
  - [`.env.example`](file:///D:/work/flatmate/.env.example) (Local development)
  - [`.env.staging.example`](file:///D:/work/flatmate/.env.staging.example) (Isolated staging environment)
  - [`.env.production.example`](file:///D:/work/flatmate/.env.production.example) (Hardened production deployment)
- **Masking & Sanitization:** All CI/CD logs automatically mask GitHub Repository Secrets. CI/CD runs execute security scanners that fail builds if high-entropy strings or private keys match known patterns.

---

## 2. Cloud Secret Storage Matrix

Staging secrets are stored in managed secret vaults rather than plaintext file systems:

| Secret Identifier | Target Cloud Vault | Injected Service | Description & Permissions |
|---|---|---|---|
| `DATABASE_URL` | GCP Secret Manager / Vercel Env | Cloud Run Backend | Transaction pooler URI (`postgresql+asyncpg://...:6543/postgres`). |
| `DIRECT_URL` | GCP Secret Manager | Cloud Run / Alembic Runner | Direct PostgreSQL port 5432 connection string for DDL schema migrations. |
| `SUPABASE_URL` | Vercel / GCP Secret Manager | Web & Backend | Supabase API endpoint (`https://<project-ref>.supabase.co`). |
| `SUPABASE_ANON_KEY` | Vercel Env (Public) | Web Frontend (`NEXT_PUBLIC_`) | Public anonymous client key constrained by Supabase Row-Level Security. |
| `SUPABASE_SERVICE_ROLE_KEY` | GCP Secret Manager | Backend Cloud Run ONLY | Superuser service-role key. **NEVER exposed to frontend bundle or browser.** |
| `SUPABASE_JWT_SECRET` | GCP Secret Manager | Backend Cloud Run | Shared HMAC-SHA256 secret for verifying user JWT signatures. |
| `SECRET_KEY` | GCP Secret Manager | Backend Cloud Run | Internal cryptographic fallback and CSRF session signing key. |
| `REDIS_URL` | GCP Secret Manager | Backend Cloud Run | Redis connection string with TLS (`rediss://...`). |
| `RESEND_API_KEY` | GCP Secret Manager | Backend Cloud Run | Transactional email provider API key. |

---

## 3. Cryptographic Verification & Rotation Protocol

1. **Secret Generation:**
   - Secrets are generated using cryptographically secure pseudorandom number generators:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(48))"
     ```
2. **Access Control:**
   - The Cloud Run staging runtime service account (`livora-staging-sa@tradebit-396406.iam.gserviceaccount.com`) is granted only `roles/secretmanager.secretAccessor` on the specific staging secret versions.
3. **Automated Audit:**
   - Security workflow `.github/workflows/security.yml` runs automated secret pattern scanning and verifies that no service-role keys exist in frontend source bundles or client artifacts.
