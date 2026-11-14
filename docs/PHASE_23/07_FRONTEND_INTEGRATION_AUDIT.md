# PHASE 23.6 — Complete Frontend Integration Audit

**Document Version:** 1.0  
**Phase:** 23.6 — Frontend Route & UI Component Integration Audit  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Frontend Architect, Accessibility & UX Engineer, API Integration Specialist  
**Classification:** Frontend Route Architecture & User Journey Verification  
**Application:** Next.js 14 App Router (`apps/web`)  
**Shared Packages:** `@flatmate/contracts`, `@flatmate/ui`  

---

## 1. Executive Summary

This audit assesses the frontend integration of all 32 App Router routes, form handlers, state management hooks, error/empty states, and API bindings against backend endpoints and contracts.

In strict compliance with **Non-Negotiable Rule 0**:
- **Zero Dead Controls:** Every visible button, modal, form input, and interactive card connects to a real handler, dispatches an API request, or modifies local state.
- **Contract Synchronization:** Frontend data transfer objects (DTOs) strictly conform to `@flatmate/contracts` and backend Pydantic schemas.
- **Enterprise Client Infrastructure:** `apps/web/lib/api-client.ts` centralizes RFC 7807 problem details parsing, transparent token refresh, request correlation headers, and abort signal timeouts.

---

## 2. Complete 32-Route Inventory & Functionality Matrix

| Route Path | Type | Primary User Journey | Centralized Client Usage | Error & Loading States |
| :--- | :--- | :--- | :--- | :--- |
| `/` | Static (○) | Landing page, hero search, Indian cities | `apiClient.get('/properties')` | Skeleton cards, empty search |
| `/(auth)/login` | Static (○) | User authentication & role redirect | `supabase.auth.signInWithPassword` | Inline error banner, spinner |
| `/(auth)/register` | Static (○) | Account creation & role onboarding | `apiClient.post('/auth/register')` | Field validation, disabled state |
| `/(auth)/forgot-password`| Static (○) | Password recovery email dispatch | `apiClient.post('/auth/forgot-password')` | Success alert, error banner |
| `/(auth)/reset-password` | Static (○) | Password update with reset token | `apiClient.post('/auth/reset-password')` | Password strength, error state |
| `/properties` | Static (○) | Marketplace property discovery | `apiClient.post('/search/properties')` | Filter drawer, loading skeleton |
| `/properties/[id]` | Dynamic (ƒ)| Property details, booking enquiry | `apiClient.get('/properties/:id')` | 404 RFC 7807 boundary, image carousel |
| `/flatmates` | Static (○) | Flatmate search & discovery feed | `apiClient.post('/search/flatmates')` | Compatibility badges, empty match |
| `/flatmates/[id]` | Dynamic (ƒ)| Flatmate profile, compatibility view | `apiClient.get('/matching/compatibility/:id')` | Dimension radar/bar, like/pass |
| `/matches` | Static (○) | Mutual matches & incoming interactions | `apiClient.get('/matching/matches')` | Empty state, chat trigger button |
| `/groups` | Static (○) | Flatsharing syndicate formation | `apiClient.get('/groups/')` | Syndicate list, modal form |
| `/dashboard` | Static (○) | Multi-role user portal | `apiClient.get('/auth/me')` | Role-based widget switches |
| `/profile` | Static (○) | Profile & lifestyle questionnaire | `apiClient.put('/profiles/me')` | 10-dimension sliders, toast |
| `/onboarding` | Static (○) | First-time profile & quiz wizard | `apiClient.post('/profiles/me/quiz')` | Stepper wizard, progress bar |
| `/messages` | Static (○) | Direct & group chat, attachments | WebSocket + `/messaging/*` | Typing status, read receipts |
| `/appointments` | Static (○) | Property viewing schedule & status | `apiClient.get('/appointments/')` | Calendar list, status pills |
| `/owner` | Static (○) | Owner portal landing | Role guard (`owner`, `pg_operator`)| Action cards, stats preview |
| `/owner/dashboard` | Static (○) | Landlord listings & applications | `apiClient.get('/owners/dashboard')` | Occupancy charts, applicant list |
| `/owner/listings/create` | Static (○) | Multi-step property creation | `apiClient.post('/properties/')` | Multi-image upload, inventory |
| `/tenants` | Static (○) | Tenant vacancy replacement portal | `apiClient.get('/tenants/vacancies')` | Vacancy cards, apply button |
| `/tenants/vacancies/create`| Static (○) | Post flatmate replacement vacancy | `apiClient.post('/tenants/vacancies')`| Preference form, date picker |
| `/pg` | Static (○) | Paying Guest (PG) operator portal | Role guard (`pg_operator`, `admin`)| Capacity meters, room matrix |
| `/pg/manage` | Static (○) | Bed & room inventory allocation | `apiClient.post('/pg/buildings')` | Bed status grid, assign modal |
| `/admin` | Static (○) | System governance & metrics | Role guard (`admin`, `super_admin`) | KPI dashboard, user table |
| `/admin/moderation` | Static (○) | Content & safety moderation queue | `apiClient.get('/moderation/reports')` | Resolve/action modal, report list |
| `/about` | Static (○) | Mission & platform information | Static content | Responsive typography |
| `/help` | Static (○) | FAQ & user support knowledgebase | Accordion components | Searchable topic index |
| `/safety` | Static (○) | Scam prevention & anti-fraud guide | Security alerts & reporting advice | Visual advisory cards |
| `/privacy` | Static (○) | DPDP Act 2023 compliance policy | Structured legal disclosure | Consent retraction instructions |
| `/terms` | Static (○) | Terms of Service agreement | Legal agreement text | Section navigation |
| `/sitemap.xml` | Route Handler| Dynamic search index metadata | Metadata generation | XML format compliant |
| `/_not-found` | Static (○) | RFC 7807 404 error fallback | Standard error UI | Home redirection link |

---

## 3. Centralized API Client Architecture (`apps/web/lib/api-client.ts`)

1. **Configurable Base URL:** Defaults to `process.env.NEXT_PUBLIC_API_URL` or `http://localhost:8000/api/v1`.
2. **RFC 7807 Problem Details Parsing:** Automatically maps HTTP 4xx/5xx responses to `ApiError` instances containing `status`, `title`, `detail`, `errorCode`, `invalidParams`, and `requestId`.
3. **Transparent Token Refresh:** Intercepts 401 Unauthorized responses, synchronizes token renewal across concurrent calls, and transparently retries original requests.
4. **Request Correlation & Cancellation:** Automatically attaches `X-Request-Id` UUID headers and supports caller-provided `AbortSignal` for user search debouncing and component unmounting.
5. **No Secret Leakage:** Never reads or transmits service-role keys; uses strictly user Bearer tokens.

---

## 4. UI Quality, Accessibility & Responsive Standards

- **Responsive Design:** Mobile-first layout implemented across all pages using Tailwind CSS responsive prefixes (`sm:`, `md:`, `lg:`, `xl:`). Tested down to 360px viewport width.
- **Indian Market Localization:**
  - Currency formatting via `Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })`.
  - Lakhs & Crores compact formatting supported (`formatIndianCompactCurrency`).
  - Dates and timestamps formatted in Indian Standard Time (IST, UTC+5:30).
  - Indian phone numbers validated against 10-digit formats with +91 country code masking.
- **Accessibility:** Semantic HTML tags (`<main>`, `<nav>`, `<section>`, `<article>`), ARIA labels on icon buttons, form labels associated with inputs (`htmlFor`), keyboard navigability.
