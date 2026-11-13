# Product Requirements Document (PRD)

**Product Name:** Flatmate Platform  
**Status:** Approved  
**Version:** 1.0.0  
**Target Audience:** Urban Young Professionals, University Students, Property Owners, Master Tenants  

---

## 1. Executive Summary

Finding a compatible flatmate is notoriously stressful, inefficient, and fraught with safety concerns. Traditional classifieds (Craigslist, Facebook Groups) lack personality verification, lifestyle compatibility matching, and safety guarantees.

**Flatmate Platform** solves this by delivering an end-to-end matching and co-living platform. By combining vector-embedded lifestyle preference matching (sleep patterns, cleanliness, sociability, remote-work habits, dietary choices, and pet tolerances) with PostGIS spatial property discovery, real-time messaging, and verified background credentials, Flatmate Platform streamlines finding an ideal living companion and securing quality rental accommodation.

---

## 2. Target Personas

### Persona A: The Solo Seeker (Priya, 24)
- **Role:** Junior Software Engineer relocating to a new metro area.
- **Goals:** Find a tidy, quiet flatmate within a \$1,200/month budget who works normal business hours.
- **Pain Points:** Scared of internet scams, awkward roommate interviews, misaligned expectations on cleanliness and guests.

### Persona B: The Existing Flatmate / Room Poster (Marcus, 28)
- **Role:** Digital Marketer holding an existing 2-bed apartment lease whose roommate relocated.
- **Goals:** Quickly fill the vacant private room with a reliable, friendly individual who respects shared spaces and pays rent on time.
- **Pain Points:** Inundated with dozens of unqualified or incompatible messages on social media.

### Persona C: The Group Syndicates ("Team-Up to Rent") (Alex & Jordan, 22)
- **Role:** Recent graduates teaming up to lease a 3-bedroom flat together to achieve lower per-person rent.
- **Goals:** Find a matching 3rd flatmate with similar lifestyle habits to apply jointly for larger rental properties.

### Persona D: The Property Landlord / Master Host (Elena, 45)
- **Role:** Small-scale property investor managing 4 co-living units.
- **Goals:** Maintain high occupancy rates, screen verified tenants, receive transparent group rental applications.

---

## 3. Core Functional Requirements

### 3.1 Authentication & Profile Identity
- Multi-channel auth: Email/Password, Google OAuth, Apple ID.
- Mandatory 2-step onboarding:
  1. Personal information & verified student/work credentials.
  2. The **Lifestyle Matrix Questionnaire**:
     - Sleep schedule: Early bird vs. Night owl (scale 1-5).
     - Cleanliness standards: Relaxed vs. Ultra-organized (scale 1-5).
     - Guest & party frequency: Rarely, Weekends, Anytime.
     - Work-from-home intensity: In-office, Hybrid, 100% Remote.
     - Dietary/Kitchen habits: Vegan, Vegetarian, Omnivore, Halal, Kosher.
     - Substance habits: Smoking/Vaping (Never, Outside only, Allowed), Alcohol habits.
     - Pet policy & ownership: Dogs, Cats, None, Allergies.

### 3.2 Algorithmic Matching Engine
- **Lifestyle Vector Embedding**: Embed seeker lifestyle vectors into a multidimensional space (64-dimensional float array stored via `pgvector`).
- **Composite Compatibility Score (0-100%)**:
  $$Score = w_{vector} \cdot S_{cos} + w_{budget} \cdot S_{budget} + w_{loc} \cdot S_{loc} + w_{dealbreakers} \cdot S_{filter}$$
- **Dealbreaker Filters**: Hard non-negotiables (gender preference, smoking inside, pet allergies) immediately exclude incompatible candidates.
- **Match Breakdown Radar**: Visual presentation showing compatibility across 5 distinct axes: Cleanliness, Schedule, Sociability, Budget, and Habits.

### 3.3 Property & Room Discovery
- Listing Types:
  - Private Room in Shared Apartment.
  - Shared Room / Studio.
  - Entire Property for Flatmate Groups.
- PostGIS Geospatial Radius & Bounding Box Queries.
- Filters: Price range, Move-in date, Lease duration, Amenities (In-unit laundry, Dishwasher, AC, Gym, High-speed WiFi), Furnished status.
- Media upload: Multi-image carousel with virtual tour support.

### 3.4 Flatmate Group Formation ("Team-Ups")
- Create a hunting group with a target neighborhood and budget.
- Invite compatible seekers to form a joint syndicate.
- Shared wishlist: Group members can vote (Upvote/Downvote/Comment) on prospective properties.
- Joint Application: Submit a single combined rental application package to landlords.

### 3.5 Real-Time Communication
- Asynchronous WebSockets via Redis Pub/Sub.
- Direct 1-on-1 chats and Flatmate Group channels.
- In-chat listing sharing and rental application status updates.
- Typing indicators, online presence, and delivery/read receipts.

### 3.6 Trust, Verification & Safety
- Identity Verification badge (Govt ID, passport check via Stripe Identity or Persona mock).
- University/Employer email domain verification (`.edu`, corporate domains).
- User reviews & past flatmate testimonials.
- Moderation system: User reporting, listing fraud detection, automated profanity & scam keyword filtering.

---

## 4. Non-Functional Requirements

| Metric | Target |
| :--- | :--- |
| **P95 API Latency** | < 120ms for search & match calculations |
| **Real-Time Latency** | < 50ms for message delivery over WebSocket |
| **Availability (SLA)** | 99.9% uptime |
| **Mobile Responsiveness** | Seamless across iPhone/Android screens (>=320px) |
| **Accessibility** | WCAG 2.1 AA compliant |
| **Security Standards** | OWASP Top 10 mitigation, bcrypt cost factor 12, encrypted tokens |

---

## 5. Success Metrics & KPIs
1. **Match-to-Conversation Rate**: > 35% of high-score matches (>80%) start a chat.
2. **Time-to-Sign**: Median time from account creation to accepted room application < 18 days.
3. **Safety Incident Rate**: < 0.05% reported abuse incidents across active chats.
4. **Retention & Satisfaction**: > 85% positive post-move-in compatibility survey score.
