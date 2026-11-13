# Phase 20 Infrastructure Cost & Resource Optimization Analysis

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** Principal Cloud Architect & Finance Ops  

---

## 1. Staging Environment Cost Analysis (Free-First Architecture)

In adherence to mandatory operating principles ("Prefer free-first infrastructure while maintaining a migration path to scalable infrastructure"), the staging topology was designed to maximize modern cloud free-tier allocations:

| Service Component | Provider | Tier & Included Allowances | Estimated Monthly Usage (Staging) | Staging Monthly Cost |
|---|---|---|---|---|
| **Web Frontend** | Vercel | Hobby / Staging Free Tier (100GB bandwidth, unlimited builds) | ~15 GB bandwidth, 80 builds/month | **$0.00** |
| **API Backend** | Google Cloud Run | GCP Free Tier (2M requests, 360,000 vCPU-seconds, 180,000 GiB-seconds free/month) | ~250,000 requests, 45,000 vCPU-seconds (scale-to-zero) | **$0.00** |
| **Container Registry** | Google Artifact Registry | Free storage up to 0.5 GB/month | ~420 MB compressed image storage | **$0.00** |
| **Cloud Build** | Google Cloud Build | 120 free build-minutes per day | ~25 build-minutes per week | **$0.00** |
| **Primary Database** | Supabase | Free Tier (500 MB database, 2 projects, pause on inactivity disabled) | ~65 MB synthetic seed + PostGIS indexes | **$0.00** |
| **Object Storage** | Supabase Storage | 1 GB storage, 2 GB egress included free | ~120 MB synthetic photos & test PDFs | **$0.00** |
| **Redis Cache / PubSub** | Upstash Redis | Serverless Free Tier (10,000 commands/day) | ~2,500 commands/day | **$0.00** |
| **Transactional Email** | Resend | Free Developer Tier (3,000 emails/month, 100/day) | ~400 verification/appointment emails | **$0.00** |
| **Total Staging Spend** | — | — | — | **$0.00 / month** |

---

## 2. Production Scaled Cost Forecast (Phase 21 Transition)

When migrating from staging to a commercial production environment serving 10,000 to 50,000 active monthly users:

| Production Resource | Recommended Tier | Estimated Monthly Cost | Scaling Trigger / Threshold |
|---|---|---|---|
| **Vercel Pro (Frontend)** | Vercel Team Tier | $20.00 / seat | Custom domains, SLA, 1TB bandwidth. |
| **Cloud Run (Backend)** | Pay-as-you-go (`min-instances=1`) | $15.00 – $35.00 | 1 instance warm standby to prevent cold starts. |
| **Supabase Pro (Database)** | Supabase Pro Plan | $25.00 | 8GB disk, daily PITR backups, compute add-ons. |
| **Upstash Redis Pro** | Pay-as-you-go | $5.00 – $10.00 | High-frequency PubSub socket distribution. |
| **Resend Email Pro** | Paid Plan (50k emails/month) | $20.00 | Dedicated IP and higher sending rates. |
| **Domain & DNS** | Cloudflare Registrar | ~$10.00 / year ($0.85/mo) | Commercial `.in` or `.com` domain with DDoS guard. |
| **Total Production Estimate** | — | **~$85.00 – $120.00 / month** | Sustains 50,000 MAU and 1,000 concurrent sessions. |
