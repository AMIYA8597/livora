# BACKEND MASTER IMPLEMENTATION PLAN
## Flatmate Compatibility & Rental Marketplace

**Document:** Backend Engineering Master Plan  
**Version:** 1.0  
**Execution:** Sequential, test-driven, production-oriented  
**Backend:** Python + FastAPI  
**Database:** Supabase PostgreSQL  
**ORM:** SQLAlchemy 2.x  
**Migrations:** Alembic  
**Authentication:** Supabase Auth  
**Geospatial:** PostGIS  
**Testing:** pytest  
**Development Environment:** Antigravity Pro  
**Infrastructure Strategy:** Free-first, provider-independent architecture

---

# PART A — MASTER ENGINEERING INSTRUCTIONS

## 1. Role and Principles
- Operating with production engineering discipline.
- No superficial demonstration backend or fake implementations.
- No skipped requirements, hardcoded production responses, or placeholder endpoints.
- Full security, multi-role RBAC, PostGIS geospatial indexing, and Alembic migrations.
- Modular monolith using clean architectural boundaries:
  1. API / Presentation Layer (`app/api/v1/`)
  2. Application / Use-Case Service Layer (`app/modules/*/service.py`)
  3. Domain Layer (`app/modules/*/models.py`, `schemas.py`)
  4. Infrastructure Layer (`app/infrastructure/`, `app/core/`)

## 2. Product Context & Target Domain (India-First)
- **User Roles:** Students, Working Professionals, Researchers, Freelancers, Property Owners, Existing Tenants, PG Operators, Brokers, Property Managers, Admins, Super Admins (Multi-role support per user).
- **Accommodation Inventory:**
  - 1RK, 1BHK, 2RK, 2BHK, 3BHK, 4BHK+, Studio, Independent House, Private Room, Shared Room, PG, Hostel, Co-living.
  - Multi-tier structural distinction: Property -> Unit -> Room -> Bed with explicit capacity invariants (`current_occupants <= max_capacity`, `occupied_beds <= max_beds`).
- **Explainable 10-Factor Compatibility Engine:**
  - Working Schedule: 15%
  - Sleep Schedule: 15%
  - Budget: 15%
  - Cleanliness: 12%
  - Lifestyle (Smoking/Drinking/Pets): 12%
  - Noise & Lighting: 10%
  - Guest & Social Habits: 7%
  - Food & Cooking: 5%
  - Professional Domain: 5%
  - Location: 4%
  - *Hard Dealbreakers:* Incur score cap ($\le 30.0$) with human-readable conflict explanations.

---

# PART B — PHASE ROADMAP

- **Phase 0:** Repository Inspection & Baseline Audit
- **Phase 1:** Backend Foundation & Project Architecture
- **Phase 2:** Database Architecture & Migrations
- **Phase 3:** Identity, Authentication & RBAC
- **Phase 4:** User, Professional & Lifestyle Profiles
- **Phase 5:** Property & Accommodation Domain
- **Phase 6:** Owner, Existing Tenant & PG Workflows
- **Phase 7:** Geospatial Search & Discovery
- **Phase 8:** Flatmate Compatibility Engine
- **Phase 9:** Group Flatmate Matching
- **Phase 10:** Applications, Enquiries & Appointments
- **Phase 11:** Messaging & Notifications
- **Phase 12:** Verification, Safety & Administration
- **Phase 13:** AI/ML Readiness & Fallbacks
- **Phase 14:** Production Hardening & Performance
- **Phase 15:** Final End-to-End Verification
