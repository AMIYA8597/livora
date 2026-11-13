# Phase 18 Known Issues & Operational Considerations

**Project:** Flatmate Compatibility & Rental Marketplace  
**Phase:** Phase 18 — Product Experience Engineering  
**Date:** November 14, 2026  
**Status:** ALL CRITICAL & HIGH DEFECTS RESOLVED  

---

## 1. Resolved Baseline Defects in Phase 18

1. **Asyncpg Multi-Command Statement Syntax:**
   - *Issue:* Alembic migration `002_messaging_realtime_system.py` combined multiple `CREATE TABLE` and `CREATE INDEX` queries into single `op.execute(...)` calls, causing `asyncpg.exceptions.PostgresSyntaxError`.
   - *Resolution:* Split all table and index declarations into individual `op.execute(sa.text(...))` statements. Migration applies cleanly.
2. **Missing Property Address Masking in Seeker View:**
   - *Issue:* Properties previously returned unmasked `address_exact` to all API callers.
   - *Resolution:* `PropertyService._format_property_response` now masks exact addresses for non-owners and unconfirmed visitors, fuzzing geographic coordinates to preserve DPDP Act 2023 privacy.
3. **Empty / Non-Interactive Routes:**
   - *Issue:* Static and placeholder pages lacked interactive actions or real backend persistence.
   - *Resolution:* All 32 routes fully wired to live FastAPI endpoints with proper error handling, empty states, and toast notifications.

---

## 2. Low-Priority Operational Considerations & Future Backlog

1. **Browser Native Web Push Notifications:**
   - *Description:* While in-app notifications and real-time WebSocket messaging are fully operational, browser service-worker web push notifications (VAPID) can be added in a future phase for background mobile alerts when the tab is closed.
   - *Workaround:* Live notification drawer in `Navbar.tsx` and polling/WebSocket connection in `ChatWindow.tsx` keep active sessions informed.
2. **Third-Party Map Tile Integration (Mapbox / Google Maps):**
   - *Description:* Properties display locality tags, fuzzed coordinates, and distance calculations. A visual interactive canvas map with clustered pins can be integrated via Mapbox GL JS / Leaflet in a dedicated mapping enhancement phase.
3. **Automated WhatsApp Notification Bridge:**
   - *Description:* Many Indian users prefer instant WhatsApp alerts for visit confirmations and match notifications. Integrating an official WhatsApp Business API webhook service can enhance user engagement.
4. **Offline PWA Caching:**
   - *Description:* Standard Service Worker caching for offline viewing of previously loaded properties and chat history can be enabled for low-connectivity Indian regions.
