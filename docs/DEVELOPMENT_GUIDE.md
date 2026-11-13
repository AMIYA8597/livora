# Developer Onboarding & Development Guide

Welcome to the Flatmate Platform engineering team! This guide will walk you through setting up your local environment, running the monorepo services, executing tests, and adhering to coding standards.

---

## 1. Prerequisites

Before beginning, ensure you have the following installed:
- **Node.js**: `v20.x` or higher
- **pnpm**: `v9.x` (`corepack enable && corepack prepare pnpm@latest --activate`)
- **Python**: `v3.11` or higher
- **Docker & Docker Compose**: v2.20+
- **Git**

---

## 2. Initial Setup

### 2.1 Clone and Setup Environment Variables
```bash
git clone https://github.com/flatmate/flatmate-platform.git
cd flatmate-platform

# Copy the environment file template
cp .env.example .env
```

### 2.2 Install Frontend & Monorepo Dependencies
```bash
pnpm install
```

### 2.3 Setup Python Virtual Environment for Backend
```bash
cd apps/api
python -m venv .venv

# Activate on Linux/macOS:
source .venv/bin/activate

# Activate on Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Install dependencies in editable mode
pip install -e .
cd ../..
```

---

## 3. Running with Docker Compose (Recommended)

Start the databases, cache, object storage, and services:
```bash
docker compose up -d postgres redis minio
```

Check health:
```bash
docker compose ps
```

---

## 4. Database Migrations & Seeding

Run the automated migration and seed script:
```bash
# Unix:
./scripts/seed_db.sh

# Windows PowerShell:
.\scripts\seed_db.ps1
```

Or manually with Alembic:
```bash
cd apps/api
source .venv/bin/activate
alembic upgrade head
python ../../database/seeds/seed.py
```

---

## 5. Running the Development Servers

You can run both web and backend services simultaneously using Turborepo from the root:
```bash
pnpm dev
```

Or run them individually:

### Backend API:
```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```
- OpenAPI Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- OpenAPI ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Frontend Next.js:
```bash
cd apps/web
pnpm dev
```
- Web Application: [http://localhost:3000](http://localhost:3000)

---

## 6. Project Conventions & Architecture

### Backend Domain-Driven Module Pattern
Each domain module inside `apps/api/app/modules/<module_name>/` follows a clean structure:
```
module_name/
├── __init__.py
├── models.py       # SQLAlchemy 2.0 ORM models
├── schemas.py      # Pydantic v2 validation DTOs
├── service.py      # Core business logic & database transactions
└── router.py       # FastAPI router endpoints & dependency injection
```

### Frontend Feature Structure
`apps/web/` utilizes Next.js 14 App Router:
- `app/`: Route pages, layouts, and route handlers.
- `components/`: UI building blocks (e.g., `PropertyCard`, `MatchBadge`).
- `features/`: Complex domain-specific components with internal state.
- `hooks/`: Reusable custom React hooks (`useAuth`, `useSocket`).
- `lib/`: Utilities, constants, and API client.

---

## 7. Testing & Linting

### Running Backend Tests
```bash
cd apps/api
pytest -v
```

### Running Frontend Tests & Linting
```bash
pnpm test
pnpm lint
```

### Formatting Code
```bash
pnpm format
```
