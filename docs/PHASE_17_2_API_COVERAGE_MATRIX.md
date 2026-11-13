# Phase 17.2 API Coverage & Integration Matrix

**Project:** Flatmate Compatibility & Rental Marketplace  
**Phase:** Phase 17 — Frontend–Backend Integration  
**Stage:** Phase 17.2 — API Contract Synchronization & Full Coverage  
**Timestamp:** 2026-11-13  
**Status:** 100% VERIFIED & SYNCHRONIZED  

---

## 1. Overview

This matrix documents the complete API coverage of the Flatmate Compatibility & Rental Marketplace, detailing every FastAPI endpoint, its Pydantic schemas, TypeScript DTO contracts, consumer frontend routes, and automated verification tests.

All endpoints operate against real PostgreSQL/Supabase database tables with strict RFC 7807 problem details error handling.

---

## 2. API Coverage Matrix

| HTTP Method | API Endpoint | Backend Module | Request Schema | Response Schema | Frontend Route / Component | Automated Test Coverage | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | `auth` | `RegisterRequest` | `TokenResponse` | `/register` | `test_auth.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/auth/login` | `auth` | `LoginRequest` | `TokenResponse` | `/login` | `test_auth.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/auth/refresh` | `auth` | `RefreshTokenRequest` | `TokenResponse` | `apiClient` refresh handler | `test_auth.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/auth/forgot-password` | `auth` | `ForgotPasswordRequest` | `dict` | `/forgot-password` | `test_auth.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/auth/reset-password` | `auth` | `ResetPasswordRequest` | `dict` | `/reset-password` | `test_auth.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/profiles/me` | `profiles` | None | `ProfileResponse` | `/profile`, `/dashboard` | `test_profiles_lifestyle.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `PUT` | `/api/v1/profiles/me` | `profiles` | `ProfileUpdate` | `ProfileResponse` | `/profile`, `/onboarding` | `test_profiles_lifestyle.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/profiles/me/privacy` | `profiles` | None | `PrivacySettingsResponse` | `/profile` | `test_profiles_lifestyle.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `PUT` | `/api/v1/profiles/me/privacy` | `profiles` | `PrivacySettingsUpdate` | `PrivacySettingsResponse` | `/profile` | `test_profiles_lifestyle.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/lifestyle/me` | `lifestyle` | None | `LifestyleResponse` | `/profile`, `/onboarding` | `test_profiles_lifestyle.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `PUT` | `/api/v1/lifestyle/me` | `lifestyle` | `LifestyleCreateOrUpdate`| `LifestyleResponse` | `/profile`, `/onboarding` | `test_profiles_lifestyle.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/lifestyle/dealbreakers` | `lifestyle` | None | `List[DealbreakerResponse]` | `/profile`, `/onboarding` | `test_profiles_lifestyle.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/lifestyle/dealbreakers` | `lifestyle` | `DealbreakerCreate` | `DealbreakerResponse` | `/profile`, `/onboarding` | `test_profiles_lifestyle.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `DELETE`| `/api/v1/lifestyle/dealbreakers/{id}` | `lifestyle` | None | `dict` | `/profile` | `test_profiles_lifestyle.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/storage/upload` | `storage` | `multipart/form-data` | `UploadResponse` | `FileUpload.tsx`, `/profile`, `/owner/listings/create` | `test_storage_upload.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/storage/signed-url` | `storage` | `SignedUrlRequest` | `SignedUrlResponse` | `PropertyCard.tsx`, `/properties/[id]` | `test_storage_upload.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/properties/` | `properties` | Query params (city, rent, bhk) | `List[PropertyResponse]` | `/properties`, `/` | `test_properties_domain.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/properties/` | `properties` | `PropertyCreate` | `PropertyResponse` | `/owner/listings/create` | `test_properties_domain.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/properties/{id}` | `properties` | Path param (`id`) | `PropertyResponse` | `/properties/[id]` | `test_properties_domain.py`, `property_detail.test.ts` | VERIFIED |
| `PATCH`| `/api/v1/properties/{id}` | `properties` | `PropertyUpdate` | `PropertyResponse` | `/owner/dashboard` | `test_properties_domain.py`, `test_security_regressions.py` | VERIFIED |
| `GET` | `/api/v1/matching/compatibility/{id}` | `matching` | Path param (`target_id`) | `CompatibilityResponse` | `/flatmates/[id]`, `/matches` | `test_matching.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/matching/interactions` | `matching` | `InteractionRequest` | `InteractionResponse` | `/flatmates`, `/matches` | `test_matching.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/matching/matches` | `matching` | None | `List[MutualMatchResponse]` | `/matches`, `/dashboard` | `test_matching.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/groups/` | `groups` | Query params | `List[GroupResponse]` | `/groups` | `test_group_matching.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/groups/` | `groups` | `GroupCreate` | `GroupResponse` | `/groups` | `test_group_matching.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/groups/{id}/members` | `groups` | `AddMemberRequest` | `GroupMemberResponse` | `/groups` | `test_group_matching.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/groups/{id}/wishlist/{prop_id}/vote` | `groups` | `VoteRequest` | `WishlistItemResponse` | `GroupWishlistCard.tsx` | `test_group_matching.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/groups/{id}/compatibility` | `groups` | None | `GroupCompatibilityResponse`| `/groups` | `test_group_matching.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/applications/` | `applications` | `ApplicationCreate` | `ApplicationResponse` | `/properties/[id]` | `test_applications_appointments.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/owners/applications` | `owners` | None | `List[ApplicationReviewResponse]` | `/owner/dashboard` | `test_owner_tenant_pg_workflows.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `PATCH`| `/api/v1/applications/{id}/status` | `applications` | `ApplicationStatusUpdate`| `ApplicationResponse` | `/owner/dashboard` | `test_applications_appointments.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/appointments/` | `appointments` | None | `List[AppointmentResponse]` | `/appointments` | `test_applications_appointments.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/appointments/` | `appointments` | `AppointmentCreate` | `AppointmentResponse` | `/properties/[id]`, `/appointments` | `test_applications_appointments.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `PATCH`| `/api/v1/appointments/{id}/status` | `appointments` | `AppointmentStatusUpdate`| `AppointmentResponse` | `/appointments` | `test_applications_appointments.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/messaging/conversations` | `messaging` | None | `List[ConversationResponse]`| `/messages` | `test_phase20a_messaging_system.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/messaging/conversations` | `messaging` | `CreateConversationRequest` | `ConversationResponse` | `/properties/[id]`, `/messages` | `test_phase20a_messaging_system.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `GET` | `/api/v1/messaging/conversations/{id}/messages` | `messaging` | Query params (`cursor`, `limit`)| `MessageListResponse` | `ChatWindow.tsx`, `/messages` | `test_phase20a_messaging_system.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/messaging/messages` | `messaging` | `SendMessageRequest` | `MessageResponse` | `ChatWindow.tsx`, `/messages` | `test_phase20a_messaging_system.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/tenants/vacancies` | `tenants` | `ExistingTenantVacancyCreate` | `VacancyResponse` | `/tenants/vacancies/create` | `test_owner_tenant_pg_workflows.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/pg/buildings` | `pg_management`| `PGBuildingCreate` | `PGBuildingResponse` | `/pg/manage` | `test_owner_tenant_pg_workflows.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/pg/buildings/{id}/floors` | `pg_management`| `PGFloorCreate` | `PGFloorResponse` | `/pg/manage` | `test_owner_tenant_pg_workflows.py`, `test_phase17_e2e_integration.py` | VERIFIED |
| `POST` | `/api/v1/moderation/reports` | `moderation` | `ReportCreate` | `ReportResponse` | `ReportModal.tsx` | `test_verification_moderation_admin.py`, `test_phase17_e2e_integration.py`| VERIFIED |
| `GET` | `/api/v1/moderation/reports` | `moderation` | Query params (`status`) | `List[ReportResponse]` | `/admin/moderation` | `test_verification_moderation_admin.py`, `test_phase17_e2e_integration.py`| VERIFIED |
| `PATCH`| `/api/v1/moderation/reports/{id}` | `moderation` | `ReportReviewRequest` | `ReportResponse` | `/admin/moderation` | `test_verification_moderation_admin.py`, `test_phase17_e2e_integration.py`| VERIFIED |
| `GET` | `/api/v1/admin/stats` | `administration` | None | `PlatformStatsResponse` | `/admin` | `test_verification_moderation_admin.py`, `test_phase17_e2e_integration.py`| VERIFIED |
