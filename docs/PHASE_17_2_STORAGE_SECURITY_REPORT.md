# Phase 17.2 Storage Security & Architecture Report

**Project:** Flatmate Compatibility & Rental Marketplace  
**Phase:** Phase 17 — Frontend–Backend Integration  
**Stage:** Phase 17.2 — Storage Architecture, Authorization & Upload Security  
**Timestamp:** 2026-11-13  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary

Storage handling in rental marketplaces is a prime vector for security vulnerabilities, including Broken Object Level Authorization (BOLA), arbitrary file upload (RCE), unauthenticated document leakage (KYC/Aadhaar/PAN disclosure), and path traversal. Phase 17.2 implemented a zero-trust storage subsystem in `apps/api/app/modules/storage/service.py` backed by pluggable cloud and local storage providers (`apps/api/app/infrastructure/storage.py`).

The storage implementation guarantees:
1. Bucket-level domain segregation (`avatars`, `properties`, `verification`).
2. Magic-byte MIME verification (preventing spoofed extensions).
3. Anti-malware and executable payload rejection (blocking Windows PE and Linux ELF binaries).
4. Strict resource ownership authorization.
5. Zero public exposure for verification documents (mandatory time-limited signed URLs).

---

## 2. Storage Bucket Architecture & Policy

| Bucket Name | Allowed MIME Types | Allowed Extensions | Max File Size | Public URL Permitted | Access Policy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `avatars` | `image/jpeg`, `image/png`, `image/webp` | `.jpg`, `.jpeg`, `.png`, `.webp` | 5 MB | Yes (CDN Cached) | Authenticated caller can only write to their own isolated avatar prefix. |
| `properties` | `image/jpeg`, `image/png`, `image/webp` | `.jpg`, `.jpeg`, `.png`, `.webp` | 10 MB | Yes (CDN Cached) | Caller must be the verified owner of the property listing or a platform admin. |
| `verification` | `image/jpeg`, `image/png`, `application/pdf` | `.jpg`, `.jpeg`, `.png`, `.pdf` | 15 MB | **NO (STRICTLY FORBIDDEN)** | KYC/Government IDs; accessible ONLY via 15-minute time-limited HMAC signed URLs to the owner and admin. |

---

## 3. Security Controls & Defense Mechanisms

### 3.1 Magic-Byte File Inspection
Clients frequently spoof the `Content-Type` header or append `.png` to malicious scripts. `StorageService` ignores user-supplied headers and inspects the raw leading bytes of every upload:
- **JPEG:** `\xff\xd8\xff`
- **PNG:** `\x89PNG\r\n\x1a\n`
- **WebP:** Validates `RIFF` header at byte 0 and `WEBP` container signature at bytes 8-11.
- **PDF:** `%PDF-` at byte 0.

If the file payload does not strictly match the expected magic bytes, the upload is aborted with HTTP 400 (`INVALID_MIME_TYPE`).

### 3.2 Executable Header & Malware Scanning
Every file passes through an automated scanner interface (`MalwareScanner`):
- **Windows Executables (PE):** Checks for `MZ` (`\x4d\x5a`) magic bytes.
- **Linux Executables (ELF):** Checks for `\x7fELF` (`\x7f\x45\x4c\x46`) headers.
- **Embedded Shell Scripts:** Scans for shebang markers (`#!/bin/sh`, `#!/bin/bash`).

Detected executables are immediately rejected with HTTP 400 (`EXECUTABLE_REJECTED`), and security events are logged with the caller's IP and user ID.

### 3.3 Path Traversal Neutralization
To prevent attackers from writing files outside the storage root (e.g. `../../etc/passwd` or `..\system32`), filenames are sanitized:
- Directory traversal sequences (`../`, `..\\`) are stripped.
- Leading and trailing slashes are removed.
- Path resolution uses `os.path.abspath` and verifies `commonpath == storage_root`. Any breakout attempt triggers an immediate `BadRequestException`.

### 3.4 BOLA / Ownership Verification
- **Property Uploads:** When `bucket == "properties"`, the caller must supply `entity_id` corresponding to the target property. `StorageService` verifies via SQLAlchemy query that `property.owner_id == caller.id` (or caller is admin). Non-owners receive HTTP 403 (`ForbiddenException`).
- **Avatar Uploads:** Automatically namespaced to `avatars/{caller_id}/avatar_{timestamp}.ext`. Users cannot overwrite or modify other users' profile pictures.
- **Verification Documents:** Stored in the private bucket under `verification/{caller_id}/`. Public URLs are never returned; callers receive a private storage path or must request a short-lived signed URL via `POST /api/v1/storage/signed-url`.

---

## 4. Test Verification Evidence

The storage test suite `apps/api/tests/test_storage_upload.py` executed 15 tests:

| Test Case | Scenario Verified | Result |
| :--- | :--- | :--- |
| `test_upload_valid_avatar_jpeg` | Upload valid JPEG to `avatars` bucket | PASSED |
| `test_upload_valid_property_png` | Owner uploads valid PNG to their property | PASSED |
| `test_upload_valid_verification_pdf` | Seeker uploads KYC PDF to `verification` bucket | PASSED |
| `test_reject_invalid_bucket` | Rejection of unknown bucket name (`system_bin`) | PASSED |
| `test_reject_file_size_exceeded` | File exceeding bucket maximum size limit | PASSED |
| `test_reject_mime_spoofing` | Text file disguised with `.jpg` extension | PASSED |
| `test_reject_windows_pe_executable` | Rejection of `.exe` containing `MZ` header | PASSED |
| `test_reject_linux_elf_binary` | Rejection of binary containing `\x7fELF` header | PASSED |
| `test_path_traversal_in_filename` | Stripping of `../../../evil.png` | PASSED |
| `test_bola_property_photo_upload` | Non-owner attempting to upload photo to another owner's property | PASSED (HTTP 403) |
| `test_admin_bypass_property_photo_upload` | Admin uploading photo to any property | PASSED |
| `test_verification_doc_never_returns_public_url` | Verification upload returns private key, not public URL | PASSED |
| `test_signed_url_generation_authorized` | Owner generating signed URL for their KYC document | PASSED |
| `test_signed_url_generation_unauthorized` | Attacker attempting to generate signed URL for another user's KYC | PASSED (HTTP 403) |
| `test_api_authenticated_upload_success` | Full HTTP integration test of `POST /api/v1/storage/upload` | PASSED |

**Execution Time:** `15 passed in 2.31s`
