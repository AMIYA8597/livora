# Phase 20 Frontend Deployment Architecture & Vercel Integration

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** Frontend Deployment Engineer & SRE  

---

## 1. Next.js 14 Build & Route Optimization

The frontend web application was built and optimized using Next.js 14 App Router and Turborepo.

### Production Build Metrics
- **Compilation:** 32 routes compiled cleanly with 0 TypeScript errors.
- **Shared JavaScript Footprint:** 87.1 kB First Load JS shared by all routes.
- **Route Breakdown:**
  - `○ /` (Home / Landing): 7.37 kB (122 kB First Load)
  - `○ /flatmates`: 2.97 kB (118 kB First Load)
  - `ƒ /flatmates/[id]`: 7.68 kB (114 kB First Load - dynamic server-rendered)
  - `○ /properties`: 8.78 kB (118 kB First Load)
  - `ƒ /properties/[id]`: 6.01 kB (112 kB First Load - dynamic server-rendered)
  - `○ /messages`: 11.3 kB (113 kB First Load - WebSocket & real-time messaging)
  - `○ /dashboard`: 10.9 kB (120 kB First Load)
  - `○ /owner/dashboard`: 6.33 kB (115 kB First Load)
  - `○ /pg/manage`: 6.32 kB (108 kB First Load)
  - `○ /admin/moderation`: 6.58 kB (115 kB First Load)

---

## 2. Vercel Staging Configuration

The deployment is configured via [`apps/web/vercel.json`](file:///D:/work/flatmate/apps/web/vercel.json):

```json
{
  "framework": "nextjs",
  "buildCommand": "pnpm build",
  "installCommand": "pnpm install",
  "outputDirectory": ".next",
  "regions": ["bom1", "hnd1"],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Robots-Tag", "value": "noindex, nofollow" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" }
      ]
    }
  ]
}
```

---

## 3. Security Headers & Search Engine Protection

In [`apps/web/next.config.mjs`](file:///D:/work/flatmate/apps/web/next.config.mjs), enterprise security headers are enforced across all staging routes:
- `X-Frame-Options: DENY`: Prevents clickjacking attacks.
- `X-Content-Type-Options: nosniff`: Prevents MIME-confusion attacks.
- `Referrer-Policy: strict-origin-when-cross-origin`: Restricts referrer leakage.
- `X-Robots-Tag: noindex, nofollow`: Guarantees staging environments do not dilute production SEO or leak staging records to search engines.
- `public/robots.txt`:
  ```
  User-agent: *
  Disallow: /
  ```
- Image Security: Remote images restricted strictly to `images.unsplash.com` and `*.supabase.co`.
