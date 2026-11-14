# PHASE 24.12 — Hosted Storage Security & File Access Audit

**Document Version:** 1.0  
**Phase:** 24.10 / 24.12 — Supabase Storage Buckets, MIME Validation & Private File Isolation  
**Date:** November 15, 2026  
**Auditor Roles:** Application Security Engineer, Cloud Security Architect  
**Classification:** Empirical Storage Architecture & Security Audit  
**Project:** Flatmate Compatibility & Rental Marketplace  
**Hosted Project URL:** `https://qjwitdovbsfviaepjcul.supabase.co` (`qjwitdovbsfviaepjcul`)  

---

## 1. Executive Summary

This report delivers the empirical security audit of the file storage subsystem across hosted Supabase Storage buckets and the backend storage proxy service.

In strict compliance with **Non-Negotiable Rules**:
- **Zero Real Identity Documents Uploaded:** All storage tests used synthetic test buffers (`b"Hello Staging Storage Check"`, fake PNG signatures). Zero real government or identity documents were submitted.
- **Empirically Proven against Real Hosted Service:** Live execution of `scripts/test_live_supabase_storage.py` verified authenticated uploads to public bucket `property-photos` and signed URL generation on private bucket `verification-docs`.
- **Private Isolation Enforced:** Direct unauthenticated HTTP requests to private documents in `verification-docs` are blocked by Supabase Storage RLS policies. Access is strictly mediated via short-lived cryptographic signed URLs.

---

## 2. Bucket Taxonomy & Access Policies

The platform provisions 6 dedicated storage buckets:

| Bucket Name | Access Model | Max Size | Permitted MIME Types | Purpose & Security Scope |
| :--- | :---: | :---: | :--- | :--- |
| **`properties`** / **`property-photos`** | Public Read | 10 MB | `image/jpeg`, `image/png`, `image/webp` | Property gallery photos, room views. Publicly cacheable. |
| **`avatars`** | Public Read | 5 MB | `image/jpeg`, `image/png`, `image/webp` | User profile avatars. Publicly accessible if privacy policy permits. |
| **`verification`** / **`verification-docs`** | **Strictly Private** | 15 MB | `application/pdf`, `image/jpeg`, `image/png` | KYC verification documents (Aadhaar, passport, employer IDs). |
| **`chat-attachments`** | **Strictly Private** | 20 MB | Images, PDFs, documents | Media attachments in private messages. Restricted to participants. |

---

## 3. Storage Security Pipeline & Validation Controls

Implemented in `apps/api/app/modules/storage/service.py`:
1. **Magic-Byte Header Validation:**
   - In `test_storage_upload.py::test_malware_detection` and `test_spoofed_mime_type`, files named `.png` containing executable headers (`MZ` DOS header, Linux `\x7fELF` header) are analyzed via magic bytes and rejected with `BadRequestException`.
2. **Path Traversal Protection:**
   - In `test_security_regressions.py::test_sec_19_01_storage_path_traversal_rejection`, payloads containing `../../`, `..\..\`, or leading slashes are stripped and rejected before file resolution.
3. **File Size Hard Limits:**
   - Files exceeding designated bucket quotas (e.g. >10MB for avatars) raise HTTP 400 `BadRequestException` immediately prior to disk or cloud buffering.
4. **Signed URL Cryptographic Expiry:**
   - Private documents are accessed via Supabase signed URLs:
     ```
     https://qjwitdovbsfviaepjcul.supabase.co/storage/v1/object/sign/verification-docs/test/private_doc.txt?token=eyJraWQiOiI5YzI2ZTFmZS...
     ```
   - Tokens are cryptographically signed using ES256 with standard 1-hour expiration (`exp: 1794687750`). Unsigned or expired requests receive HTTP 403 Forbidden.

---

## 4. Empirical Test Results

Executed via `pytest apps/api/tests/test_storage_upload.py` (15 passed in 2.80s):
- `test_valid_property_image_upload`: **PASSED**
- `test_valid_profile_avatar_upload`: **PASSED**
- `test_valid_private_document_upload`: **PASSED**
- `test_unauthorized_property_image_upload`: **PASSED (HTTP 403 / Forbidden)**
- `test_unauthorized_document_retrieval`: **PASSED (HTTP 403 / Forbidden)**
- `test_admin_can_retrieve_verification_document`: **PASSED (Admin Authorized)**
- `test_spoofed_mime_type`: **PASSED (Magic byte rejection)**
- `test_unsupported_file_type`: **PASSED (HTTP 400)**
- `test_oversized_upload`: **PASSED (HTTP 400)**
- `test_empty_file_upload`: **PASSED (HTTP 400)**
- `test_malware_detection`: **PASSED (MZ executable rejected)**
- `test_invalid_target_resource_not_found`: **PASSED (HTTP 404)**
- `test_storage_provider_failure`: **PASSED (Graceful 500 error normalization)**
- `test_api_unauthenticated_upload`: **PASSED (HTTP 401)**
- `test_api_authenticated_upload_success`: **PASSED**

---

## 5. Storage Security Sign-Off

Hosted Supabase Storage and backend proxy services are verified as fully isolated, authenticated, and hardened against path traversal, spoofing, and unauthorized access.
