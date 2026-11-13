# Phase 17 — API Coverage Matrix
**Project:** Flatmate Compatibility & Rental Marketplace  
**Phase:** Phase 17 — API Integration & Contract Verification  
**Date:** November 13, 2026  

This matrix details every frontend screen, connected API endpoint, authentication requirement, persistence verification, and associated test references.

---

| Module | Frontend Screen | API Endpoint | HTTP Method | Auth Required | DB Persisted | Test Reference | Status |
|---|---|---|---|---|---|---|---|
| **Authentication** | `/register` | `/api/v1/auth/register` | `POST` | No | Yes (`users`, `user_roles`) | `test_auth.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Authentication** | `/login` | `/api/v1/auth/login` | `POST` | No | No (JWT issued) | `test_auth.py` | IMPLEMENTED AND VERIFIED |
| **Authentication** | Session Restore | `/api/v1/auth/refresh` | `POST` | No | No (JWT refreshed) | `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Authentication** | `/forgot-password` | `/api/v1/auth/forgot-password` | `POST` | No | Yes (`audit_logs`) | `test_auth.py` | IMPLEMENTED AND VERIFIED |
| **Authentication** | `/reset-password` | `/api/v1/auth/reset-password` | `POST` | No | Yes (`users.hashed_password`) | `test_auth.py` | IMPLEMENTED AND VERIFIED |
| **Profile** | `/profile` (Basic) | `/api/v1/profiles/me` | `GET`, `PUT` | Yes | Yes (`profiles`) | `test_profiles.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Profile** | `/profile` (Avatar) | `/api/v1/storage/upload` | `POST` | Yes | Yes (Storage record) | `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Profile** | `/profile` (Lifestyle) | `/api/v1/lifestyle/me` | `GET`, `PUT` | Yes | Yes (`lifestyle_profiles`) | `test_lifestyle.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Profile** | `/profile` (Dealbreakers)| `/api/v1/lifestyle/dealbreakers` | `GET`, `PUT` | Yes | Yes (`user_dealbreakers`) | `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Profile** | `/profile` (Privacy) | `/api/v1/profiles/me/privacy` | `GET`, `PUT` | Yes | Yes (`user_privacy_settings`) | `test_profiles.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Properties** | `/properties`, `/` | `/api/v1/properties/` | `GET` | No | Read (`properties`) | `test_properties.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Properties** | `/properties/[id]` | `/api/v1/properties/{id}` | `GET` | Optional | Read (`properties`, `rooms`) | `test_properties.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Properties** | `/owner` (New listing)| `/api/v1/properties/` | `POST` | Yes (`owner`, `admin`)| Yes (`properties`, `property_amenities`) | `test_properties.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Flatmates** | `/flatmates`, `/` | `/api/v1/matching/feed` | `GET` | Yes | Read (`profiles`, `users`) | `test_matching.py` | IMPLEMENTED AND VERIFIED |
| **Compatibility** | `/flatmates/[id]` | `/api/v1/matching/compatibility/{id}` | `GET` | Yes | Read (`lifestyle_profiles`) | `test_matching.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Interactions** | `/flatmates`, `/matches` | `/api/v1/matching/interactions` | `POST` | Yes | Yes (`match_interactions`, `mutual_matches`) | `test_matching.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Matches** | `/matches` | `/api/v1/matching/matches` | `GET` | Yes | Read (`mutual_matches`) | `test_matching.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Owner Portal** | `/owner` | `/api/v1/owners/dashboard` | `GET` | Yes (`owner`, `admin`)| Aggregate calculation | `test_owners.py` | IMPLEMENTED AND VERIFIED |
| **Owner Portal** | `/owner` | `/api/v1/owners/applications` | `GET` | Yes (`owner`, `admin`)| Read (`applications`) | `test_owners.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Tenants** | `/tenants` | `/api/v1/tenants/vacancies` | `GET` | No | Read (`existing_tenant_vacancies`) | `test_tenants.py` | IMPLEMENTED AND VERIFIED |
| **Tenants** | `/tenants` (Post) | `/api/v1/tenants/vacancies` | `POST` | Yes (`tenant`) | Yes (`existing_tenant_vacancies`) | `test_tenants.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **PG Management** | `/pg` | `/api/v1/pg/buildings` | `POST` | Yes (`pg_operator`, `owner`, `admin`) | Yes (`pg_buildings`) | `test_pg_management.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **PG Management** | `/pg` | `/api/v1/pg/buildings/{id}/floors` | `POST` | Yes (`pg_operator`, `owner`, `admin`) | Yes (`pg_floors`) | `test_pg_management.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Groups** | `/groups` | `/api/v1/groups/` | `POST`, `GET` | Yes | Yes (`groups`, `group_members`) | `test_groups.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Groups** | `/groups` | `/api/v1/groups/{id}/members` | `POST` | Yes | Yes (`group_members`) | `test_groups.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Groups** | `/groups` | `/api/v1/groups/{id}/wishlist/{prop_id}/vote` | `POST` | Yes | Yes (`group_wishlist_items`) | `test_groups.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Groups** | `/groups` | `/api/v1/groups/{id}/compatibility` | `GET` | Yes | Compute collective score | `test_groups.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Applications** | `/properties/[id]`, `/dashboard` | `/api/v1/applications/` | `POST` | Yes | Yes (`applications`) | `test_applications.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Applications** | `/dashboard` | `/api/v1/applications/me` | `GET` | Yes | Read (`applications`) | `test_applications.py` | IMPLEMENTED AND VERIFIED |
| **Applications** | `/owner` | `/api/v1/applications/{id}/status` | `PATCH` | Yes (Owner/Applicant) | Yes (`applications.status`) | `test_applications.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Appointments** | `/properties/[id]`, `/dashboard` | `/api/v1/appointments/` | `POST` | Yes | Yes (`appointments`) | `test_appointments.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Appointments** | `/dashboard` | `/api/v1/appointments/me` | `GET` | Yes | Read (`appointments`) | `test_appointments.py` | IMPLEMENTED AND VERIFIED |
| **Appointments** | `/dashboard` | `/api/v1/appointments/{id}/status` | `PATCH` | Yes (Host/Visitor) | Yes (`appointments.status`) | `test_appointments.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Messaging** | `/properties/[id]`, `/messages` | `/api/v1/messaging/conversations` | `POST`, `GET` | Yes | Yes (`conversations`, `conversation_participants`) | `test_messaging.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Messaging** | `/messages` | `/api/v1/messaging/messages` | `POST` | Yes (Participant) | Yes (`messages`) | `test_messaging.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Messaging** | `/messages` | `/api/v1/messaging/conversations/{id}/messages` | `GET` | Yes (Participant) | Read (`messages`) | `test_messaging.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Moderation** | `/flatmates/[id]`, `/admin` | `/api/v1/moderation/reports` | `POST`, `GET` | Yes | Yes (`moderation_reports`) | `test_moderation.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Moderation** | `/admin` | `/api/v1/moderation/reports/{id}` | `PATCH` | Yes (`admin`, `super_admin`) | Yes (`moderation_reports.status`) | `test_moderation.py`, `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
| **Admin** | `/admin` | `/api/v1/admin/stats` | `GET` | Yes (`admin`, `super_admin`) | Aggregate live stats | `test_phase17_e2e_integration.py` | IMPLEMENTED AND VERIFIED |
