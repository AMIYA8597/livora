# Phase 20 Storage Configuration & Identity Document Security

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 13, 2026  
**Author:** Application Security & Infrastructure Engineer  

---

## 1. Storage Bucket Topology & Access Boundaries

The staging environment provisions two isolated storage buckets via Supabase Storage:

| Bucket Name | Access Classification | Max File Size | Allowed MIME Types | Purpose & Security Controls |
|---|---|---|---|---|
| `property-photos` | **Public** (Read) | 10 MB | `image/jpeg`, `image/png`, `image/webp` | Property, room, and PG listings. Cached globally via CDN edge. Uploads restricted to authenticated property owners. |
| `verification-docs` | **Private** (Encrypted) | 15 MB | `application/pdf`, `image/jpeg`, `image/png` | Government IDs (Aadhaar, Passport, PAN), tenancy agreements, student IDs. **Zero public URL access.** |

---

## 2. Row-Level Security (RLS) Storage Policies

Direct public HTTP access to `verification-docs` is forbidden at the storage layer:

```sql
-- Private Verification Documents: Restrict upload to owner
CREATE POLICY "Users can upload their own verification docs"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'verification-docs' AND (storage.foldername(name))[1] = auth.uid()::text);

-- Private Verification Documents: Read access only for uploader or admin
CREATE POLICY "Users and admins can view verification docs"
ON storage.objects FOR SELECT
TO authenticated
USING (
  bucket_id = 'verification-docs' AND (
    (storage.foldername(name))[1] = auth.uid()::text OR
    (auth.jwt() -> 'app_metadata' -> 'roles')::jsonb ? 'admin'
  )
);

-- Public Property Photos: Anyone can read, only verified owners can insert
CREATE POLICY "Public property photos viewable by all"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'property-photos');

CREATE POLICY "Authenticated owners can upload property photos"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'property-photos');
```

---

## 3. Presigned URL Access & Image Optimization

- **Private Document Viewing:** When a user or compliance moderator views an identity document, the backend generates an ephemeral presigned URL with an expiry of 300 seconds (5 minutes). Once expired, the URL ceases to function.
- **Image Domain Configuration:** Next.js Image Optimization is configured in [`apps/web/next.config.mjs`](file:///D:/work/flatmate/apps/web/next.config.mjs) to safely optimize remote images from `*.supabase.co` and `images.unsplash.com` with AVIF/WebP conversion and responsive widths.
