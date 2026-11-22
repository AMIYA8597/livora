# Production Launch Gap List

Collected 2026-11-22 from the actual source code (not the phase reports).
Work these top to bottom. Mark each `[x]` only when code + tests land.

## P0 — Blocks launch

- [ ] **1. Hosted schema not yet applied.** *(Waiting on owner.)* The Supabase project is
      reachable again over HTTPS (auth, JWKS and storage verified), but Postgres ports time out
      from the dev network, so migrations must run from GitHub Actions. The owner adds the
      `STAGING_DATABASE_URL` secret to the `staging` environment (session pooler, port 5432),
      then runs the `hosted-db-migration.yml` workflow, or pastes
      `database/migrations/complete_hosted_schema.sql` into the Supabase SQL editor.
- [x] **2. Test hacks in production code.** *(Done: AsyncMock branches removed, block checks always run.)* `matching/service.py` checks
      `type(self.db).__name__ != "AsyncMock"`, so code paths differ between tests and production
      (block filtering is skipped in tests).
- [x] **3. Matching does not scale.** *(Done.)* Recommendations are now two-stage. Stage 1 is one
      SQL query that excludes self, blocks in both directions, inactive accounts, private
      profiles, matched-only profiles without a match, and budgets more than 25% apart, ordered by
      pgvector cosine distance (HNSW index, migration `003_pgvector_matching`). Stage 2 re-ranks
      the top 200 exactly. The N+1 lookups are removed, and a single private profile no longer
      breaks the endpoint for everyone. Real-DB tests are in
      `tests/test_matching_recommendations_db.py`. *Caveat: pgvector is not installed locally,
      so the ANN path is exercised only in CI (pgvector is now installed there) and on Supabase.*
- [x] **3b. PostGIS was faked when missing.** *(Done.)* Migration 001 now requires real PostGIS.
      Migration `004_real_postgis_location` converts databases that got the fakes:
      `properties.location`, `cities.center_location` and `localities.center_location` become
      `geometry(Point,4326)`, the shim functions and domain are dropped, and a GiST index is
      added on `location::geography`. Radius search now filters and sorts in PostGIS **before**
      pagination (previously it paginated first, then filtered in Python). The silent Bengaluru
      default coordinates are removed. Real-PostGIS tests are in `test_search_geospatial.py`.
      PostGIS 3.7.0 is installed natively on the dev machine.
- [x] **3c. Seed data was broken.** *(Done.)* Both old seeds (`01_seed_data.sql`,
      `staging_seed.py`) referenced columns that no longer exist, and `seed.py` plus the Docker
      init mount applied a competing raw-SQL schema. Now Alembic is the only schema path, and
      `database/seeds/seed.py` is ORM-based and idempotent: 4 cities, 10 localities and 11
      listings at real coordinates, plus 8 seekers with distinct lifestyles. It refuses
      production, and refuses remote hosts without `--allow-remote`. `test_seed_db.py` guards it.
      The legacy raw SQL migrations were removed (they remain in git history).
- [ ] **3e. Dev DB holds 278 test-generated users and 60 duplicate listings** from test runs made
      before the tests were isolated. They need cleaning up (owner's call: it deletes local data).
- [ ] **3d. pgvector not installed natively.** *(Blocked: needs Visual Studio Build Tools, a multi-GB install, for a source build; owner to decide.)* Migration 003's vector index is skipped on the
      dev machine (there are no official Windows binaries; it needs a Visual Studio build or the
      Docker image `infrastructure/docker/Dockerfile.postgres`). CI and Supabase have it.
- [x] **4. No transactional email.** *(Done.)* `app/infrastructure/email/` has Resend (HTTPS
      API, idempotency keys, retries on 429/5xx only), SMTP (Mailpit in docker-compose, inbox at
      :8025) and in-memory providers. In-memory is refused outside dev/test, and an unknown or
      misconfigured provider fails at startup instead of dropping mail. Templates HTML-escape
      every value and strip CR/LF from subjects. Sends are fail-safe (logged, never raised) and run
      after the response through BackgroundTasks. Wired events: password reset link, password
      changed, application received (owner), application status changed (applicant), visit
      requested (host). Tests are in `tests/test_email.py`.
- [x] **4a. Password reset tokens leaked and were reusable.** *(Done.)* The API returned the
      reset token whenever `DEBUG` was on, and staging ran with `DEBUG=True`, so anyone could
      reset any account. Tokens could also be replayed for their whole 15 minutes. Now the token
      is delivered only by email (echoed only in development/test), and it carries a keyed
      fingerprint of the current password hash, so it is single-use and every outstanding token
      dies when the password changes.
- [ ] **4b. OTP verification accepts a hard-coded code.** `AuthService.verify_otp` accepts
      `1234`/`123456` in every environment, so any phone number can be "verified". Needs a real
      SMS/OTP provider with hashed, expiring, rate-limited codes, gated to dev/test (pairs with 12).
- [x] **5. Workers are stubs.** *(Done.)* Real background processing built on a transactional
      outbox (`app/workers/outbox.py`, migration `006_outbox_dispatch`). Emails are written to
      `outbox_events` before the response, so a crash or provider outage can no longer lose them.
      The dispatcher claims due rows with `FOR UPDATE SKIP LOCKED` plus a 5-minute lease (no
      transaction stays open across network calls, and a dead worker's rows come back). It retries
      with exponential backoff up to 1 h, dead-letters after 8 attempts, and scrubs payloads after
      delivery (reset links, message text). Requests kick a dispatch right after responding, and
      Celery beat sweeps every 15 s. Hourly maintenance purges old outbox rows, expires lapsed
      subscriptions, and cancels unconfirmed visits 24 h past their time. The `message.created`
      events messaging was already writing are now consumed (the hook for offline notifications,
      item 9). Celery runs with `acks_late`, prefetch 1 and time limits, plus a `beat` service in
      docker-compose. *Not built:* match precompute. Recommendations are a live pgvector HNSW
      query, so a cache would only add staleness until metrics show a need.
- [x] **5b. Uploaded photos leaked GPS location.** *(Done.)* Images are decoded and re-encoded on
      upload (`app/infrastructure/images.py`): EXIF/GPS is stripped, orientation is applied,
      decompression bombs (over 40 MP) are rejected, the declared type must match the content,
      and trailing polyglot payloads are dropped. Previously a phone photo of a flat exposed its
      exact coordinates, defeating the platform's location fuzzing.
- [x] **6. Next.js 14.2.4 had 42 security advisories (4 critical).** *(Done.)* Next 14 is
      end-of-life, and many fixes exist only in 15.5.29 or later, so a 14.2.x patch could not clear
      them. Upgraded to Next 16.4.6 and React 19.3 (plus postcss and lucide-react), renamed
      `middleware.ts` to `proxy.ts` (the Next 16 convention), and moved ESLint to a flat config on
      ESLint 9. `pnpm audit --prod`: 0 vulnerabilities. The build, 31 web tests, a production-server
      smoke test of every route type and a browser check (no hydration errors) all pass. CI now
      runs lint (errors fail the build) and `pnpm audit --audit-level high`. The new React Compiler
      lint rules also found a stale-closure risk in the socket reconnect and an impure render;
      both are fixed.

- [x] **2b. Test suite ran against the hosted DB and storage.** `tests/conftest.py` now forces a
      local `flatmate_test` DB plus local storage, and refuses non-local hosts. Result: 136/136
      passing (previously 133 passed, 3 failed).
- [x] **2c. Storage silently fakes success.** *(Done: raises `StorageConfigurationError`; tests in `test_storage_config.py`.)* If the Supabase client fails to initialise,
      `SupabaseStorageProvider` returns `mock.supabase.co` URLs instead of failing. It must raise
      outside dev/test.

- [x] **2d. CI would have failed.** There were 12 existing mypy errors in messaging (the README
      claimed 0). Fixed. CI now passes `TEST_DATABASE_URL`, installs pgvector, and checks the
      migration downgrade/upgrade round-trip. Later fixes: `apps/web/lib` was gitignored, the API
      packaging and dependencies were incomplete, ruff 0.17 defaults were pinned, Node is 24, and
      pgvector installs from the PGDG archive (bullseye moved off the main PGDG host).
- [x] **2d-ii. Staging deploy reported fake success.** *(Done.)* Jobs with missing secrets now show
      as skipped with a warning naming each missing secret. Migrations run before the backend,
      and a real `/health/ready` smoke test gates the result.
- [x] **2e. Chat showed the oldest messages.** `get_messages` sorted ascending before applying
      LIMIT, so long chats never showed new messages. It now returns the latest page in
      chronological order (`test_messaging_pagination_db.py`).

- [x] **2f. CRITICAL: Supabase Data API was wide open.** *(Done.)* No migration enabled RLS, so
      a hosted deploy would have exposed every table (password hashes, KYC, messages) through
      PostgREST to the public anon key. The hand-written `rls_policies.sql` was never applied,
      covered only 21 of 44 tables, and leaked active users' rows. Migration
      `005_lockdown_data_api` enables RLS on every table and revokes all anon/authenticated
      privileges, including default privileges for future tables. The backend, as table owner,
      is unaffected. Tested in `test_data_api_lockdown_db.py`.
- [x] **2g. Backend connected as the `postgres` owner.** *(Done in code; owner action needed on
      Supabase.)* Migration `007_least_privilege_app_role` creates a NOLOGIN group role
      `flatmate_app`. It has DML on application tables only: no DDL, TRUNCATE, TRIGGER or
      REFERENCES, read-only `alembic_version`, and no BYPASSRLS. Each table gets a
      `flatmate_app_all` RLS policy for that role alone (anon/authenticated still have none).
      `migrations/env.py` re-applies this after every migration run (and skips it below 007, so
      downgrades stick), so new tables can never miss RLS or the app grant.
      `scripts/create_app_db_user.sql` creates the login with `statement_timeout=15s` and
      `idle_in_transaction_session_timeout=30s`. Alembic uses `MIGRATION_DATABASE_URL` (owner);
      the API uses `DATABASE_URL` (the login). Outside dev/test, startup logs a SECURITY error if
      the API connects with owner/superuser rights. **The whole test suite now runs as a restricted
      login**, and `test_least_privilege_db.py` proves DDL, privilege escalation and
      `alembic_version` tampering are refused. CI also runs the real login script and checks it
      with psql. *Owner action:* after the hosted migration, run the script on Supabase, put the
      login URL (user `flatmate_api.<project-ref>`) in the runtime secret
      `STAGING_APP_DATABASE_URL`, and keep the owner URL only in the GitHub migration secret.
- [ ] **2h. Supabase Storage bucket policies are unverified.** Check that the KYC/avatars buckets
      are private and that only the backend's service role can write.

## P1 — Required for a quality product

- [ ] **7. Frontend architecture.** 30 pages but only 8 components, and the largest pages are
      about 1,000 lines (`dashboard`, `profile`, `properties/[id]`). Split them into feature
      components, add a shared layout/shell, and handle loading, error and empty states.
      Add a shared data-fetching hook to replace the 17 fetch-in-effect patterns (lint rule
      `react-hooks/set-state-in-effect` is set to warn until then), and replace 13
      `window.location.href` full-page navigations with router navigation.
- [ ] **8. Responsive and mobile UX audit.** Check every route at 320, 375, 768, 1024 and 1440px:
      a mobile bottom nav, a full-screen mobile chat, and touch targets of at least 44px.
- [ ] **9. Live chat completeness.** Verify reconnect/backoff, offline queueing, read receipts,
      typing and presence end to end in the browser, plus image attachments in chat and
      push/email when the user is offline.
- [ ] **10. AI/ML is mostly heuristic or mock.** `MockExternalML*` providers. Add a real
      embedding-based "about me"/listing semantic search, learning-to-rank from like/pass
      interactions, an LLM-assisted scam/abuse moderation provider, and a smart reply/icebreaker
      feature in chat. Add offline evaluation metrics.
- [ ] **11. Payments and subscriptions.** Only the models exist. Needs a Razorpay (INR)
      integration: plans API, checkout, signed webhook verification, entitlement checks.
- [ ] **12. Identity verification is mocked.** Integrate a real KYC provider, or clearly gate
      the feature off.
- [ ] **13. Web push and in-app notification centre.**
- [ ] **13b. Admins cannot override application status.** `PATCH /applications/{id}/status`
      never passes `is_admin`, unlike appointments, so moderators cannot intervene.

## P2 — Operations and hardening

- [ ] **14. Browser E2E tests.** No Playwright. Add core journeys on mobile and desktop
      viewports in CI.
- [ ] **15. Observability.** Sentry (web + api), structured logs shipped somewhere, uptime checks.
- [ ] **16. Security pass.** CSP headers on the web app, rate limits on auth/chat/upload, file
      type sniffing and virus scan on uploads, account deletion/export (DPDP Act compliance).
- [ ] **17. SEO and performance.** Metadata/OG for property pages, image optimisation,
      Lighthouse of at least 90 on mobile.
- [ ] **18a. Deploy the worker and beat.** The staging workflow deploys only the API. Without a
      worker, emails still go out immediately (the in-request kick), but retries happen only when a
      later request triggers a dispatch, and maintenance never runs. Deploy one worker and exactly
      one beat (e.g. a Cloud Run service with always-on CPU, or Cloud Scheduler calling a Cloud
      Run job), plus a managed Redis.
- [ ] **18. Production deploy pipeline.** The staging workflow exists, but production promotion,
      backups and a tested restore do not.
