# Phase 20 Domain, DNS, TLS & HTTPS Configuration

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** Principal Cloud Architect & SRE  

---

## 1. Domain Topology & Routing Structure

To maintain clean environment isolation while avoiding upfront unbudgeted domain registration purchases, the platform supports both standard staging subdomains and managed cloud endpoints:

| Layer | Custom Domain Target | Managed Cloud Fallback URL | TLS Termination |
|---|---|---|---|
| **Frontend Web** | `staging.flatmate.internal` / `staging.livora.in` | `https://flatmate-web-staging.vercel.app` | Vercel Edge / Let's Encrypt (Automated TLS 1.3) |
| **Backend API** | `api.staging.flatmate.internal` / `api-staging.livora.in` | `https://flatmate-api-staging-<hash>.a.run.app` | Google Cloud Load Balancer / Google-managed SSL (TLS 1.3) |
| **Database** | `db.staging.flatmate.internal` | `db.<project-ref>.supabase.co:6543` | Supabase SSL / Let's Encrypt (`sslmode=require`) |
| **Object Storage** | `storage.staging.flatmate.internal` | `<project-ref>.supabase.co/storage/v1` | Supabase CDN SSL |

---

## 2. DNS Record Specifications (For Custom Domain Activation)

When the custom domain approval boundary is cleared, the following DNS records are configured in Cloudflare or the domain registrar:

```
# Frontend Vercel CNAME
CNAME   staging.livora.in      cname.vercel-dns.com.    Proxied: OFF / Auto TTL

# Backend Cloud Run CNAME (or Custom Domain Mapping)
CNAME   api-staging.livora.in  ghs.googlehosted.com.    Proxied: OFF / Auto TTL

# Verification & Email Authentication
TXT     livora.in              "v=spf1 include:resend.com ~all"
CNAME   resend._domainkey      resend._domainkey.livora.in.
```

---

## 3. TLS, Cipher Suites & HSTS Enforcement

1. **Protocol Standards:** Strict enforcement of TLS 1.3 with backward compatibility down to TLS 1.2. Legacy protocols (SSLv3, TLS 1.0, TLS 1.1) are permanently rejected.
2. **Cipher Suites:** Modern forward-secrecy cipher suites (`TLS_AES_256_GCM_SHA384`, `TLS_CHACHA20_POLY1305_SHA256`, `ECDHE-RSA-AES128-GCM-SHA256`).
3. **HTTP to HTTPS Redirection:**
   - Vercel automatically issues HTTP 308 permanent redirects to `https://`.
   - Cloud Run automatically enforces HTTPS redirection on default `.run.app` and mapped custom domains.
4. **HSTS Header:**
   - `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` is enforced on all staging and production responses.
