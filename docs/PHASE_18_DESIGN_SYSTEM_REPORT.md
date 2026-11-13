# Phase 18 Design System & UI Architecture Report

**Project:** Flatmate Compatibility & Rental Marketplace  
**Phase:** Phase 18 — Product Experience Engineering  
**Package:** `@flatmate/ui` & `apps/web`  
**Date:** November 14, 2026  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary

Phase 18 established a cohesive, India-centric design system replacing generic admin styles with a warm, trustworthy aesthetic tailored for modern Indian renters, homeowners, and PG operators. The visual identity draws inspiration from trusted architectural and rental platforms in India, emphasizing security, warmth, and clarity.

---

## 2. Brand Color Tokens & Typography

### 2.1 Palette Tokens

Defined in `packages/config/tailwind.config.base.js` and `apps/web/tailwind.config.ts`:

- **Primary Forest Green (`#173D32`):** Communicates permanence, trust, and quality. Used for primary call-to-actions, navigation headers, and hero accents.
- **Secondary Medium Forest (`#287A5A`):** Used for hover states, interactive badges, and secondary buttons.
- **Pale Sage Green (`#D9EBDD`):** Gentle background tint for verified badges, compatibility tags, and highlighted cards.
- **Warm Off-White (`#FDFBF7` / `#F5F2EA`):** Canvas background color eliminating harsh sterile clinical whites.
- **Charcoal Text (`#252B29` / `#1F2421`):** High contrast readable typography meeting WCAG AA requirements on all backgrounds.
- **Warning Gold / Saffron (`#E29578` / `#C57B57`):** Indian-inspired accent for urgent actions, deposit warnings, and dealbreakers.

### 2.2 Typography & Scale

- **Heading Font:** Inter / system geometric sans-serif with clear weights (`font-semibold`, `font-bold`).
- **Body Font:** Inter regular with relaxed line heights (`leading-relaxed`) for readability on mobile screens.
- **Micro-Copy:** High legibility labels (`text-xs font-medium tracking-wide`).

---

## 3. UI Component Library (`@flatmate/ui`)

The UI library was expanded from 7 basic components to 21 enterprise-grade accessible components:

1. **`Button`:** Variants (`primary`, `secondary`, `outline`, `ghost`, `danger`) with loading spinner state and accessible touch heights.
2. **`Badge`:** Variants (`default`, `success`, `warning`, `danger`, `outline`) for listing status, verification, and tags.
3. **`Card`:** Padded elevation surface with border accents.
4. **`Input`:** Controlled text inputs with floating error helper messages and icon slots.
5. **`Select`:** Native and styled select dropdowns with label and error support.
6. **`Checkbox`:** Accessible custom checkbox with focus ring and keyboard check support.
7. **`RadioGroup`:** Grouped radio selectors with keyboard arrow navigation.
8. **`Tabs`:** Accessible tab list and panels supporting keyboard navigation.
9. **`Modal`:** Accessible dialog overlay with focus trap, ESC key dismissal, and backdrop blur.
10. **`Drawer`:** Slide-out drawer for mobile navigation and filters with body scroll lock.
11. **`Skeleton`:** Shimmering animated placeholders replicating card and detail layouts during data fetching.
12. **`EmptyState`:** Friendly iconography, context-rich message, and actionable CTA button.
13. **`ErrorState`:** Error alert with correlation ID display and retry callback.
14. **`Pagination`:** Page number buttons, previous/next controls, and page indicator.
15. **`Tooltip`:** Hover and focus accessible micro-information popover.
16. **`Toast`:** Floating transient notification alerts with auto-dismissal.
17. **`Table`:** Responsive tabular data representation with striped rows and header contrast.
18. **`Avatar`:** User profile image with automatic initials fallback and status ring.
19. **`MatchScoreBadge`:** Circular and pill score badges color-coded by compatibility threshold (>80% green, 60-79% yellow, <60% gray).
20. **`ImageGallery`:** Multi-image responsive thumbnail strip with full-screen lightbox viewer.
21. **`LoadingIndicator`:** Lightweight SVG spinner with customizable size and color tokens.

---

## 4. Indian Marketplace Nuances

- **Currency Formatting:** `formatCurrency` renders Indian Rupee symbol `₹` and Indian comma grouping (e.g. `₹1,50,000` instead of `₹150,000`).
- **Compact Currency Notation:** `formatIndianCompactCurrency` converts numbers to Lakhs (`₹1.5 L`) and Crores (`₹1.2 Cr`).
- **Timezone Standardization:** `formatDateTimeIST` displays all appointments and visit times in Indian Standard Time (IST / UTC+05:30).
- **Phone Formatting:** `formatIndianPhoneNumber` formats 10-digit Indian numbers with `+91` country code and masks digits for unconfirmed users (`+91 98765 •••••`).
- **Locality Search:** Pre-populated top Indian metropolitan hubs (Bengaluru, Mumbai, Delhi NCR, Hyderabad, Pune, Chennai) with popular rental localities (Indiranagar, Koramangala, HSR Layout, Whitefield, Bandra, Andheri, Gachibowli, Wakad).

---

## 5. Verification & Test Evidence

- **Frontend Unit Tests:** 31 tests passing cleanly across currency formatting, contracts integration, API client, security, and component contracts.
- **TypeScript Static Verification:** `pnpm turbo run test` passed with 0 errors across `@flatmate/config`, `@flatmate/contracts`, `@flatmate/ui`, `@flatmate/web`.
