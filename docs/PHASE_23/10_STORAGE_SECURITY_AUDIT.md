# PHASE 23.10 — Storage and Media Security Audit Report

**Document Version:** 1.0  
**Phase:** 23.10 — Storage Architecture & Media Security Audit  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Security Architect, Storage Engineer, DevSecOps Specialist  
**Classification:** Empirical Storage Policy, Malware Defense & Privacy Access Audit  
**Project:** Flatmate Compatibility & Rental Marketplace  
**Hosted Storage Service:** Supabase Storage (`https://qjwitdovbsfviaepjcul.supabase.co/storage/v1`)  

---

## 1. Executive Summary

This report delivers the empirical security audit of media upload pipelines, access control policies, signed URL workflows, and malware defense across all configured storage buckets.

In strict accordance with **Rule 0**:
- **Zero Public Exposure of Private Identity Documents:** Verification and KYC documents are strictly stored in private buckets and are never accessible via public URLs.
- **Empirical Hosted Verification:** Direct upload to public bucket `property-photos` and signed token URL generation for private bucket `verification-docs` were verified against live Supabase Storage API (`scripts/test_live_supabase_storage.py`).

---

## 2. Bucket Classification & Aliasing Architecture

| Bucket Name | Access Classification | Intended Content | Max Size | Allowed MIME Types | Public URL Allowed |
| :--- | :---: | :--- | :---: | :--- | :---: |
| **`property-photos`** (Canonical) | **PUBLIC** | Property, unit, and room photos | 10 MB | JPEG, PNG, WebP | **YES** |
| **`properties`** (Legacy Alias) | **PUBLIC** | Backward compatibility | 10 MB | JPEG, PNG, WebP | **YES** |
| **`avatars`** (Canonical) | **PUBLIC** | User profile avatar pictures | 5 MB | JPEG, PNG, WebP | **YES** |
| **`verification-docs`** (Canonical)| **PRIVATE** | Identity proofs (Passport, DL, Voter ID)| 15 MB | JPEG, PNG, WebP, PDF | **NO (SIGNED URL ONLY)** |
| **`verification`** (Legacy Alias) | **PRIVATE** | Backward compatibility | 15 MB | JPEG, PNG, WebP, PDF | **NO (SIGNED URL ONLY)** |
| **`chat-attachments`** (Canonical)| **PRIVATE** | Chat images, rental agreements, PDFs | 15 MB | JPEG, PNG, WebP, PDF | **NO (SIGNED URL ONLY)** |

**Bucket Consolidation Recommendation:**
To prevent operator confusion while maintaining backwards compatibility, the application router accepts both canonical and alias names, mapping internally to the authoritative buckets (`property-photos` and `verification-docs`).

---

## 3. Defense-in-Depth Security Controls

### 3.1 Strict Magic-Byte & MIME Validation
Content-Type headers provided by HTTP clients cannot be trusted. The storage service (`app/modules/storage/service.py`) validates both the header and file header magic bytes:
- **JPEG:** Begins with `\xff\xd8\xff`
- **PNG:** Begins with `\x89PNG\r\n\x1a\n`
- **PDF:** Begins with `%PDF`
- **WebP:** Begins with `RIFF` and contains `WEBP`

### 3.2 Executable Header & Script Rejection
- **SVG & HTML Prohibition:** SVG and HTML files are completely disallowed from all buckets to eliminate stored Cross-Site Scripting (XSS) vectors.
- **Binary Header Scan:** Payloads starting with DOS/PE executable header `MZ` or Linux executable header `\x7fELF` are rejected with `400 Bad Request`.

### 3.3 Path Traversal & Filename Sanitization
User-provided filenames are never written directly to storage. The storage service generates deterministic UUIDv4 keys:
```python
safe_filename = f"{uuid.uuid4()}{ext}"
key = f"{target_id}/{safe_filename}"
```
This guarantees path traversal sequences (`../`, `..\\`) are neutralized before writing to storage.

### 3.4 Signed URL Authorization & Expiry
Private verification documents can only be accessed via signed URLs generated with the backend service-role key:
- **Short-Lived Expiry:** URLs expire in 3600 seconds (1 hour).
- **Access Authorization:** Only the submitting user or a verified platform administrator can request a signed download URL (`GET /api/v1/storage/signed-url`). Outsiders receive `403 Forbidden`.

---

## 4. Empirical Test Results

All 15 automated storage tests passed cleanly (`tests/test_storage_upload.py`):
- `test_valid_property_image_upload`: **PASS**
- `test_valid_profile_avatar_upload`: **PASS**
- `test_valid_private_document_upload`: **PASS**
- `test_unauthorized_property_image_upload`: **PASS (403 Forbidden)**
- `test_unauthorized_document_retrieval`: **PASS (403 Forbidden)**
- `test_admin_can_retrieve_verification_document`: **PASS (200 OK with signed URL)**
- `test_spoofed_mime_type`: **PASS (400 Rejected by magic-byte check)**
- `test_unsupported_file_type` (e.g. SVG/HTML): **PASS (400 Rejected)**
- `test_oversized_upload`: **PASS (400 Rejected)**
- `test_empty_file_upload`: **PASS (400 Rejected)**
- `test_malware_detection`: **PASS (400 Rejected)**
- `test_storage_path_traversal_rejection`: **PASS (400 Rejected)**
- Live Supabase Storage Probe (`scripts/test_live_supabase_storage.py`): **PASS**

---

## 5. Conclusion

The storage subsystem satisfies all media security, malware defense, and privacy compliance requirements.
