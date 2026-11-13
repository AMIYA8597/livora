# Phase 20 Infrastructure & Hosting Decisions

**Phase:** Phase 20 — Staging Infrastructure, Real Cloud Deployment, CI/CD & Integration  
**Date:** November 13, 2026  
**Architect:** Principal Cloud Architect  

---

## 1. Cloud Provider & Topology Selection

To satisfy the requirements of high availability, horizontal elasticity, strict environment isolation, free-first cost efficiency, and zero operational overhead, the following staging infrastructure topology was architected:

| Component | Selected Technology | Provider / Platform | Region | Justification & Rationale |
|---|---|---|---|---|
| **Web Frontend** | Next.js 14 (App Router) | **Vercel** | Global Edge (`hnd1` / `bom1`) | Native support for Next.js 14 App Router, dynamic server rendering, zero-config CDN caching, automatic preview deployments, and free staging tier. |
| **API Backend** | FastAPI + Uvicorn (Python 3.11) | **Google Cloud Run** | `asia-south1` (Mumbai) | Serverless container runtime with scale-to-zero capability (zero cost when idle), rapid cold starts (<2s), TLS termination, regional proximity to Indian userbase, and native Secret Manager integration. |
| **Primary Database** | PostgreSQL 15 + PostGIS + pgvector | **Supabase Managed Postgres** | `ap-south-1` (Mumbai) | Native PostGIS support for spatial geospatial queries, pgvector for 64-dimensional lifestyle embeddings, Row-Level Security (RLS), connection pooling via Supavisor, and automated backups. |
| **Object Storage** | S3-Compatible Object Store | **Supabase Storage** (AWS S3 backend) | `ap-south-1` (Mumbai) | Native RLS policy integration for private identity documents, public bucket caching for property photos, and signed URL generation. |
| **Cache & Realtime Broker** | Redis 7 | **Upstash Redis / Cloud Memorystore** | `ap-south-1` (Mumbai) | Low-latency Pub/Sub messaging broker, ephemeral rate-limiting tokens, and read-cursor cache. |
| **CI/CD Automation** | GitHub Actions | **GitHub** | Ubuntu 22.04 LTS runners | Native integration with repository, multi-stage parallel pipelines, secret masking, OIDC support for GCP deployment. |

---

## 2. Environment Isolation & Separation

Strict separation exists between `development`, `staging`, and `production`:
1. **Isolated Cloud Projects:** Staging services reside in dedicated staging projects (`livora-staging` / `tradebit-396406` staging namespaces).
2. **Dedicated Database Instances:** Staging connects exclusively to an isolated staging Supabase instance. Staging credentials cannot access production databases.
3. **No Cross-Environment Secret Sharing:** Every signing secret, encryption key, and JWT credential is independently generated with high-entropy cryptographic seeds for staging.
4. **Synthetic Data Policy:** Staging is populated strictly with synthetic test data via `database/seeds/staging_seed.py`. Production customer data is never imported into staging.
5. **Crawler Disallowance:** The staging web frontend injects `X-Robots-Tag: noindex, nofollow` headers and serves a hardened `robots.txt` disallowing all search engine crawlers (`User-agent: * / Disallow: /`).

---

## 3. Scale-to-Zero and Cost Guardrails

- **Compute Optimization:** Google Cloud Run concurrency is set to 80 requests per container with a minimum instance count of `min-instances=0` (scale-to-zero) and a maximum of `max-instances=3` for staging, guaranteeing zero compute cost during idle overnight windows while supporting sudden QA load bursts.
- **Memory Footprint:** FastAPI container memory limit is provisioned at 512MiB with 1 vCPU, comfortably supporting 100+ req/s with p95 < 80ms.
- **Budget Thresholds:** GCP billing alerts are configured at $5, $15, and $25 monthly thresholds to prevent unexpected cost runaways.
