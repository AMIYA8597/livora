# Phase 18 User Journey Walkthrough Report

**Project:** Flatmate Compatibility & Rental Marketplace  
**Phase:** Phase 18 — Product Experience Engineering & User Journey Finalization  
**Test Suite:** `apps/api/tests/test_phase18_e2e_acceptance.py`  
**Date:** November 14, 2026  
**Status:** COMPLETE & 100% PASSING (8/8 Journeys)  

---

## 1. Overview

Phase 18 validated all 8 end-to-end user journeys representing the full commercial lifecycle of the marketplace. Each journey was executed using realistic workflows and genuine service methods, guaranteeing zero mock data in production flows, enforced object ownership, and complete data persistence.

---

## 2. Journey Walkthroughs & Test Outcomes

### Journey A: Flatmate Seeker Discovery & Mutual Match
- **Objective:** Enable a new flatmate seeker to configure their lifestyle habits, set dealbreakers, discover compatible flatmates, evaluate the 10-D compatibility report, establish mutual interest, and access direct messaging.
- **Steps Verified:**
  1. Seeker completes 10-dimension questionnaire (sleep schedule, work arrangement, cleanliness, noise, diet, smoking, drinking, pets).
  2. Preference embedding vector generated (64-dimensional float vector).
  3. Strict dealbreaker added (`rule_key="no_smoking_inside"`, `expected_value="never"`).
  4. Compatibility computation executed against candidate profile via `compute_10_dimension_compatibility` (>80% score, dealbreakers cleared).
  5. Seeker sends "like" interaction (`is_mutual_match=False`).
  6. Candidate reciprocates with "like" interaction -> triggers automatic mutual match (`is_mutual_match=True`).
  7. Direct messaging conversation unlocked and created between the two matched participants.
- **Test Function:** `test_phase18_journey_a_flatmate_seeker_discovery_and_match` -> **PASSED**

---

### Journey B: Owner Property Inventory Lifecycle
- **Objective:** Enable a property owner to create a multi-room, multi-bed listing, toggle listing status, evaluate rental applications, confirm physical visits, and manage occupancy.
- **Steps Verified:**
  1. Owner creates property listing with 2BHK configuration, pricing, deposit, amenities, and room/bed inventory (`RoomCreate`, `BedCreate`).
  2. Initial listing status verified as `published`.
  3. Owner toggles status to `paused` -> verified via `update_listing_status`.
  4. Seeker submits rental application with proposed rent and move-in date.
  5. Owner accepts application with personalized note.
  6. Seeker schedules viewing appointment; owner confirms visit date and time in IST.
  7. Tenant moves out -> Owner executes `vacate_bed` action, setting `is_occupied=False` and decrementing occupant count.
- **Test Function:** `test_phase18_journey_b_owner_property_inventory_lifecycle` -> **PASSED**

---

### Journey C: Tenant Replacement Vacancy Lifecycle
- **Objective:** Enable an existing verified tenant to list an empty room in their shared apartment when a roommate vacates, while preventing unauthorized third parties from posting fraudulent vacancies.
- **Steps Verified:**
  1. Active lease verification check executed via `TenantMembership` (`status="active"`).
  2. Tenant posts vacancy with house rules, rent, deposit, and gender preference (`preferred_gender="female"`).
  3. Seekers query vacancies with gender filter -> verified filtered results.
  4. Tenant marks vacancy filled -> `close_vacancy` sets `is_active=False`.
  5. Security negative test: Stranger without active lease attempts to create vacancy -> blocked with `ForbiddenException`.
- **Test Function:** `test_phase18_journey_c_tenant_replacement_vacancy_lifecycle` -> **PASSED**

---

### Journey D: PG Operator Building & Room Allocation
- **Objective:** Enable a PG / Coliving operator to register a multi-floor facility, configure meal plans, enforce floor gender restrictions, and set gate curfews.
- **Steps Verified:**
  1. Operator registers building with meal plans (3 meals/day, veg and non-veg), gate curfew (`23:00`), and biometric entry.
  2. Operator adds floors with gender segregation (`ladies_only`, `total_rooms=6`).
  3. Duplicate prevention: Attempt to register duplicate building on the same property is blocked with `ConflictException`.
- **Test Function:** `test_phase18_journey_d_pg_operator_building_management` -> **PASSED**

---

### Journey E: Group Syndicate Consensus & Wishlist Voting
- **Objective:** Enable friends or flatmate syndicates to form a group, evaluate group compatibility, add properties to a collective wishlist, and vote collaboratively.
- **Steps Verified:**
  1. Leader creates group (`GroupCreate`) with total budget and target move-in date.
  2. Leader invites member -> Member added with role `member`.
  3. Non-member authorization check: Stranger cannot inject members into group -> blocked with `ForbiddenException`.
  4. Group members cast up/down votes on shared wishlist property items.
  5. Group collective compatibility computation penalizes severe pairwise dealbreaker conflicts (caps group score at 30.0 if any strict conflict exists).
- **Test Function:** `test_phase18_journey_e_group_consensus_and_collective_score` -> **PASSED**

---

### Journey F: Trust, Safety, Blocking & Moderation
- **Objective:** Protect users from advance deposit / UPI scams, provide immediate block capability, and allow platform moderators to review and resolve reports.
- **Steps Verified:**
  1. Seeker reports user attempting advance deposit extortion (`reason="advance_fee_scam"`).
  2. Self-report validation: User cannot report themselves -> blocked with `BadRequestException`.
  3. Seeker immediately blocks fraudster -> `UserBlock` persisted.
  4. Blocked fraudster cannot initiate messages or interact with seeker.
  5. Platform administrator reviews report in moderation queue and applies resolution (`status="resolved"`, resolution notes logged).
- **Test Function:** `test_phase18_journey_f_trust_safety_blocking_and_moderation` -> **PASSED**

---

### Journey G: Account Recovery & Credential Management
- **Objective:** Enable users to recover access via secure password reset tokens, update verified credentials, and maintain profile details.
- **Steps Verified:**
  1. User requests password reset -> `forgot_password` generates secure JWT reset token.
  2. Generic anti-enumeration response returned to prevent account sniffing.
  3. User completes password reset with new strong password (`min_length=8`) -> `reset_password` validates token and updates password hash.
  4. User updates phone number and personal details via `UserService.update`.
- **Test Function:** `test_phase18_journey_g_account_recovery_and_credentials` -> **PASSED**

---

### Journey H: DPDP Act Privacy & Location Masking
- **Objective:** Comply with Digital Personal Data Protection (DPDP) Act 2023 by masking exact residential addresses and fuzzing geospatial coordinates for public seekers while preserving full transparency for verified owners and confirmed visitors.
- **Steps Verified:**
  1. Public/unconfirmed seeker views property:
     - `address_exact` is masked to `"[Exact address protected - revealed upon confirmed visit]"`.
     - `address_display` (locality) remains visible (`"HSR Layout Sector 2, Bengaluru"`).
     - Geographic coordinates are fuzzed to 2 decimal places to prevent pinpoint tracking.
  2. Property owner views property:
     - Exact building and flat details (`"Flat 302, Green Glen Apartments, 14th Cross"`) are fully revealed.
     - Exact unfuzzed coordinates are returned for precise map rendering.
  3. Lifestyle questionnaire raw rows are never exposed publicly; only aggregated dimension alignment scores and radar representations are shared.
- **Test Function:** `test_phase18_journey_h_dpdp_privacy_and_location_masking` -> **PASSED**

---

## 3. Test Suite Summary

- **File:** `apps/api/tests/test_phase18_e2e_acceptance.py`
- **Total Tests:** 8
- **Passed:** 8 (100%)
- **Failed:** 0
- **Execution Time:** 1.48 seconds
