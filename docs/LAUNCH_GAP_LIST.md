# Production Launch Gap List

Collected 2026-11-22 from the actual source code (not the phase reports).
Work these top to bottom. Mark each `[x]` only when code + tests land.

## Remaining before launch (collected 2026-11-24)

Gathered from the open items below and every item's "Not covered" notes.

### Code work, in order
- [x] **L1. Lifestyle answers don't reach matching.** The web form saves to `lifestyle_profiles`;
      matching, the diet and sleep filters and the ranker read `profiles.lifestyle_traits`.
      *Done:* one vocabulary in `app/modules/lifestyle/traits.py` (the form's keys and values).
      Every form save rewrites the profile copy and the matching vector in the same transaction
      and queues an embedding refresh. Old values (`vegetarian`, `omnivore`, `office`,
      `balcony_only`, quiz keys `diet`/`pets`) are converted at the API, and unknown answers get 422.
      Filters, flatmate search, embeddings text and smart replies read the form keys, and old filter
      values still work. The onboarding wizard, flatmate filter, card and profile page use the
      form's options. Migration `015_canonical_lifestyle_traits` (plain SQL, so it is also in
      `complete_hosted_schema.sql`) converts stored rows, copies saved forms onto profiles and
      recomputes vectors. Checked on a scratch database: the SQL vectors match the Python ones
      (max difference 6e-17), profiles without answers are left alone, and down/up works.
      Tests: `tests/test_lifestyle_traits.py` (10). Not covered: `lifestyle_profiles.preference_vector`
      keeps its old numbers (nothing reads it).
- [ ] **L2. Deleted or deactivated accounts keep live chat sockets** until they reconnect.
      Close them at once.
- [ ] **L3. Two WebSockets per tab** on `/messages` and `/notifications`, because the bell opens
      its own. Share one connection.
- [ ] **L4. Push failures aren't retried.** A temporary failure (timeout, 5xx, 429) should be
      retried through the outbox.
- [ ] **L5. Worker jobs inherit the API role's 15-second statement timeout.** Maintenance and
      ranker training need longer.
- [ ] **L6. `POST /search/properties` still uses plain text matching.** Use the full-text search
      the web app already uses.
- [ ] **L7. Owners and applicants can't see an application's status history**; only staff can.
- [ ] **L8. Moderators can use the moderation API but can't open the admin console.**
- [ ] **L9. No way to replay a failed Razorpay webhook** except waiting for Razorpay's retry.
- [ ] **L10. The PDF upload check reads raw bytes**, so active content inside compressed object
      streams isn't seen.
- [ ] **L11. Main-thread blocking time is 200–500ms on phones.** Load Sentry and the Supabase
      client after the page is interactive.
- [ ] **L12. Restoring a backup into hosted Supabase:** skip default-privilege entries for roles
      the restoring user can't act for.

### Needs you (accounts, keys, decisions)
- [ ] **E1. Rotate the Supabase keys and database password.** They were pasted into a chat. Do
      it before launch; then update `.env`, Secret Manager and GitHub.
- [ ] **E2. Apply the hosted schema** (item 1). Postgres ports are blocked from this network
      (checked again 2026-11-24). Either store `STAGING_DATABASE_URL` in the GitHub `staging`
      environment and run the migration workflow, or authorize the Supabase MCP connector.
- [ ] **E3. Google Cloud:**
  - Secret Manager secrets, a managed Redis and the backup bucket.
  - The GitHub environments `production` and `production-backups`.
  - The steps are in `DEPLOYMENT.md` §3 step 5 and §4.
- [ ] **E4. Domain and Vercel production settings:** `NEXT_PUBLIC_APP_URL`,
      `ENVIRONMENT=production`, the API URLs.
- [ ] **E5. Provider keys:**
  - Resend (with a verified sending domain), Twilio
  - Production VAPID keys
  - Sentry DSN and alert rules, `UPTIME_*` variables
  - Optional: Anthropic and Voyage
- [ ] **E6. Razorpay:** test keys and webhook, one test subscribe/renew/cancel, then live keys.
      Decide GST and invoices.
- [ ] **E7. Run Lighthouse** (mobile) against staging.
- [ ] **E8. Deploy ClamAV**, then set `VIRUS_SCAN_REQUIRED=true`.
- [ ] **E9. Legal review** of the DPDP rights card and the privacy page. Decide how long reports
      about deleted accounts are kept.
- [ ] **E10. pgvector on this machine** (item 3d), only if you want the vector index locally.

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
- [x] **3e. Dev DB holds 278 test-generated users and 60 duplicate listings** from test runs made
      before the tests were isolated. They need cleaning up (owner's call: it deletes local data).
      *(Done, with the owner's go-ahead.)*
      - **Backed up first:** `flatmate_db` was at schema `008` with 289 users and 71 listings.
        It was backed up with `scripts/db_backup.py` (44 tables, 2,932 rows) to
        `.claude/scratch/dev-db-backup/`, which isn't in git. The backup was restored into a
        scratch database and matched its manifest before anything was dropped.
      - **Rebuilt:** the database was recreated, migrated to `014_account_deletion` and seeded:
        - 4 cities, 10 localities
        - 11 users (admin, 2 owners, 8 seekers), 11 listings
        - 2 plans
      - **Checked:**
        - a second seed run adds nothing;
        - RLS is on all 51 tables;
        - PostGIS radius search works.
      - **To get the old data back:** create an empty database and run
        `python scripts/db_backup.py restore --dump <file> --target-url <url> --confirm-database <name>`.
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
- [x] **4b. OTP verification accepted a hard-coded code.** *(Done.)* `/auth/otp/verify` took
      `1234`/`123456` from anyone, with no login, and verified nothing. Now
      (`app/modules/auth/phone_verification.py`, migration `008_phone_verification`) both OTP
      endpoints need a logged-in user. Codes are 6 digits from `secrets`, stored only as an HMAC,
      valid 10 minutes, burned after 5 wrong guesses, and superseded by a newer code. Send limits
      live in the database: a 60-second resend cooldown and 5 sends per hour per user *and* per
      phone number (stops SMS bombing a victim from many accounts). Success sets
      `users.phone_verified_at`; a number can be verified on only one account (partial unique
      index), and changing the number clears verification. SMS goes through Twilio
      (`app/infrastructure/sms.py`); the in-memory provider is refused outside dev/test, and the
      code is echoed in the response only in dev/test. If SMS is not configured the endpoints
      return 503 (logged at startup) instead of pretending to work. The profile page has the
      send-code / enter-code flow with a resend countdown and a Verified badge. Tests are in
      `tests/test_phone_verification.py`. **Owner action before launch:** a Twilio account, a
      Messaging Service with a DLT-registered sender and template for Indian numbers, and
      `SMS_PROVIDER=twilio` plus the `TWILIO_*` secrets on staging/production.
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
- [x] **2h. Supabase Storage access.** *(Done, including the hosted bucket limits.)*
      Verified live on the hosted project: anon-key uploads to every bucket are rejected by RLS,
      anon listing returns nothing (the service key sees 16/25/12 objects), and private
      verification files return 400 to anonymous downloads. Fixed in the API:
      **(a)** IDOR: `GET /storage/signed-url` signed *any* chat-attachment path for any signed-in
      user, even after they left the conversation. It now serves only `verification` (owner or
      admin), and chat files are signed only by the membership-checked conversation endpoint.
      **(b)** The app wrote to `chat_attachments`, but the hosted bucket is `chat-attachments`, so
      chat uploads would have failed. A bucket registry (`storage_buckets.py`) now maps logical to
      physical names (`STORAGE_BUCKET_*`).
      **(c)** Any account could upload to the public `properties` bucket without a listing (free
      image hosting). This now needs a listing role or ownership of the property.
      **(d)** Startup refuses to run if a private bucket is public or missing.
      `scripts/provision_storage.py` applies per-bucket size limits and MIME allow-lists
      (applied 2026-11-22 to the hosted project: Supabase now answers 415 to an HTML or .exe
      upload and 413 to an oversized avatar).
      `scripts/check_storage_policies.py` runs in the hosted migration workflow and fails if any
      Storage policy names anon/authenticated/public. Unused buckets `property-photos` and
      `verification-docs` (one object each) are reported for the owner to review.

## P1 — Required for a quality product

- [x] **7. Frontend architecture.** *(Done.)* `dashboard`, `profile` and `properties/[id]` are
      now 160–220 lines each, built from `features/{dashboard,profile,properties}/components`.
      One auth store (`lib/auth-store.ts` via `useSyncExternalStore`) replaces a separate copy per
      `useAuth` caller. Roles come only from `/auth/me` (`roles`), not localStorage, and a network
      error no longer signs the user out. `hooks/useApiQuery` replaces every fetch-in-effect: it
      aborts superseded requests and can treat a 404 as "no data". `react-hooks/set-state-in-effect`
      and `exhaustive-deps` are now errors. Every `window.location.href` navigation is now router
      navigation, and `?next=` is checked by `safeNextPath` (no open redirect). There are
      route-level `loading`, `error`, `not-found` and `global-error` pages, and signed-out content
      no longer flashes while auth loads.
      Bugs fixed along the way:
      - Chat attachment upload used a relative URL and always got a 404.
      - Profile dealbreakers were sent without `expected_value`, so every request got a 422.
      - Saving lifestyle sent only some fields, which reset the rest.
      - The profile and dashboard forms used option values the API rejects.
      - Viewing times were sent as UTC, so 11:00 IST was booked as 16:30.
      - "Message the host" ignored `?conversationId=`.
      - The report form's default reason wasn't one of its options.
      - Tenant vacancies were posted against a hard-coded room ID. The API now defaults to the
        lease's room and rejects a room from another property.
      Left for item 8: `owner`, `owner/listings/create` and `groups` are still 580–670 lines.
- [x] **8. Responsive and mobile UX audit.** *(Done.)* Every route was measured at 320, 375,
      768, 1024 and 1440px in headless Chrome. Only `/admin/moderation` and `/tenants` overflowed
      on phones; both are fixed. Key flows were walked through at 375px against a local API.
      - **Mobile shell:** a bottom tab bar below `lg` (Discover, Flatmates, Matches, Messages,
        My Space; Home/Sign in when signed out), with safe-area padding (`viewportFit: cover`).
        The notification bell now shows on phones. On touch screens every button, select and
        input is at least 44px, and inputs use 16px text so iOS doesn't zoom.
      - **Chat:** the list and the conversation are separate full-screen views on phones, with a
        back button. Message actions appear on tap (they were hover-only).
      - **Shared UI:** `Modal` is now a real dialog (`role="dialog"`, labelled, focus moved in
        and restored). It shows as a bottom sheet on phones and its body scrolls, so a tall
        dialog's top is no longer cut off. `Input`, `Select` and `Checkbox` now generate unique
        IDs; a label-based ID collided whenever a label repeated (one "Rent" per room).
      - **Page split:** `owner` (227 lines), `owner/listings/create` (167) and `groups` (157) are
        built from `features/{owner,listings,groups}`; no `alert()` is left.
      Bugs fixed along the way:
      - The listing wizard published a fake address, coordinates, stock photo and amenities
        when left unchanged, and it skipped the room and bed inventory. It now starts empty,
        validates each step, uses real city-centre coordinates (no geocoding yet) and sends rooms
        and beds; blank bed rents split the room rent. The "quick add" form that also invented a
        location was removed.
      - Listing cards and the gallery showed Unsplash or missing placeholder images; they now say
        "No photos yet".
      - Pasting "411 045" into the PIN box, or "123 456" into the SMS code box, lost the last
        digit (`maxLength` cut the text before non-digits were stripped).
      - Groups: "Join" always failed (only leaders could add members). Self-join is allowed,
        always as `member`, and unknown roles are rejected. The wishlist now shows real listings,
        members can add one by pasting its link, and the invite instruction ("ID on their
        profile") is true: the profile shows a copyable user ID.
      - If the API was unreachable when a page loaded, a signed-in user looked signed out until
        they reloaded. The auth store now retries with backoff, and at once on `online`/`focus`.
        Network failures read "Can't reach Flatmate…" instead of "Failed to fetch".
      - The login page's demo accounts (with their password) now show only when
        `NEXT_PUBLIC_DEMO_LOGIN=true` (local dev only).
      Follow-ups:
      - Address geocoding.
      - A kitchen-policy field (the API has none).
      - Searching people for invites and listings for the wishlist.
      - An approval step for joining a group.
      - The owner portal's "revenue" showed ₹30k with no tenants.
      - *Owner action:* make sure the demo accounts `priya@example.com` and
        `sarah.owner@example.com` don't exist on the hosted database.
- [x] **9. Live chat completeness.** *(Done.)* Checked end to end with two accounts in two
      browsers: live delivery, typing, read receipts, presence, and an API outage with a message
      sent during it.
      - **Socket security:** the token now arrives in the first message instead of the URL, where
        access logs would record it. Only access tokens for active accounts are accepted; refresh
        tokens and disabled accounts used to get in. The socket closes when the token expires, and
        the client renews it and reconnects. Typing and read events need conversation
        membership; previously anyone could fake read receipts or typing in any conversation, and
        create read cursors there. Frames are size-limited, and errors no longer echo exceptions.
      - **Scale:** each socket event uses a short database session; an idle socket used to hold a
        pooled connection for its whole life. The inbox gets the last message and unread counts
        from SQL; it used to load every message of every conversation.
      - **Presence:** only shown to people you share a conversation with. It used to go to every
        connected user, and anyone could look up anyone's status. A short grace period hides
        reconnects. With Redis, presence is shared across API instances (heartbeat-scored set
        per user).
      - **Client:** reconnects with jittered backoff, and at once on `online`/tab focus. A
        silent socket counts as dead. The old reconnect loop is fixed: a replaced socket's close
        handler used to schedule another reconnect.
      - **After a reconnect:** the inbox and open conversation are refetched. Messages sent while
        offline stay queued as "Not sent · Retry" and go out by themselves when the connection
        returns; the idempotency key prevents duplicates.
      - **Read receipts:** come from the other people's read positions. One read event used to
        mark all your messages read, and loading an older page used to move your read position
        back.
      - **Offline email:** a `new_message` email (sender's name and a link, never the message
        text) goes to anyone who hasn't read a message after 10 minutes. At most one per
        conversation per hour, never if muted. In-app notifications also respect mute, which
        can now be set in the conversation details.
      - **Messages:** live events now carry attachments. Sends are plain text only (4000-character
        cap, at least text or an attachment); `system` messages and safety-warning metadata can't
        be forged.
      - **Token refresh:** a refresh that hit a network error used to sign the user out, and
        requests waiting on it hung forever. It's now one shared refresh, and only a rejected
        refresh token signs out.
      - **UI:** conversations show the other person's name, not "Flatmate Seeker". The online
        dot reflects real presence (it was always green). The phone-number safety notice was
        switched off by a hard-coded "verified" flag; it now uses the recipient's real
        verification status.
      Not covered: image upload in chat wasn't re-tried in the browser here (the upload path was
      fixed in item 7, and live events now include attachments). The 10-minute email depends on
      the outbox sweep, so it's only timely once the worker and beat run (item 18a). Web push is
      item 13.
- [x] **10. AI/ML is mostly heuristic or mock.** *(Done.)* The `MockExternalML*` providers and
      their test are gone. Everything new lives in `apps/api/app/ml/` (migration
      `009_ml_platform`). It works without any API key, and gets better when keys are set.
      - **Search:** listings (`GET /properties?q=`) and "about me" (`GET /flatmates/search?q=`)
        use hybrid search. Postgres full-text search (a weighted `search_tsv` column with a GIN
        index on listings) and embedding similarity are fused with reciprocal rank fusion. Every
        normal filter still applies, and so do privacy rules: private profiles never show,
        "matched only" needs a mutual match, and blocks hide people in both directions.
        Embeddings come from Voyage AI (`EMBEDDING_PROVIDER=voyage`, real semantic matches) or
        a local hashed n-gram model (default; lexical but typo-tolerant, e.g. "koramangla").
        Vectors are tagged with their model, so switching providers never mixes them. They are
        kept fresh through the outbox whenever a listing, bio or lifestyle changes. Supabase
        uses a pgvector HNSW index; without pgvector, search scans recent vectors with numpy.
        Backfill: `python -m app.ml.cli backfill-embeddings`. Names, phone numbers and emails are
        never embedded. Listings matching every word rank first, then listings matching only
        some of the words, so one typo or extra word doesn't empty the results. A `-word`
        exclusion applies to both full-text and embedding search; before this, embedding search
        treated "-shared" as a word to look for.
      - **Flatmate search fixes:** the city filter matched nothing for most users (it compared
        "Bengaluru" with locality names) and now matches the city's localities. Private
        profiles and blocked users used to appear in search.
      - **Learning to rank:** each like, pass and save stores the features the user saw. A
        logistic-regression ranker trains weekly (`ml.train_ranker` in beat, or
        `python -m app.ml.cli train-ranker`). It uses the 10 compatibility factors, bio
        similarity, dealbreakers and profile completeness, with a time-ordered 80/20 split. It
        goes live only if it beats the heuristic score on held-out AUC by at least 0.01, with at
        least 200 interactions. Models are versioned in `ml_models`, so rolling back means
        switching the active row. Passed people come back after 30 days, and liked or saved
        people never reappear.
      - **Moderation:**
        - Chat messages (on send and on edit) and listings first go through rules built from
          Indian rental scams: advance before a visit, "army officer will courier the keys", UPI
          ids, gift cards or crypto, OTP requests, off-platform pressure, threats and abuse.
        - A clear scam warns the recipient at once. Anything uncertain goes to Claude in the
          worker, with a little context and the content treated as data. Claude can confirm a
          warning, add one, or lift a false positive.
        - Confirmed scam or abuse opens one automatic moderation report (`source=auto`,
          idempotent).
        - Nothing is blocked or unpublished automatically.
        - Recipients see the warning under the message, live (`message.moderated` event). The
          sender never sees it.
        - The old client-side regex that blocked sending is gone.
        - Without a key, the rules alone decide.
      - **Smart replies:** a ✨ button in chat. It suggests icebreakers in an empty chat, replies
        to the last message, or a follow-up. It uses Claude when configured and otherwise falls
        back to templates built on the listing and shared lifestyle traits. Every suggestion is
        screened by the same rules (never money, OTPs, IDs or off-platform). Suggestions only
        fill the composer, never send. Membership is checked and requests are rate-limited.
      - **Claude usage:** structured JSON outputs, a short timeout, one retry, and server-side
        fallbacks to another model under load. Any failure (refusal, timeout, bad JSON) falls back
        to rules or templates, never to an error for the user. The model is set by `LLM_MODEL`
        (default `claude-opus-5-5`; `claude-haiku-5-5` costs far less for this volume).
      - **Offline evaluation:** `app/ml/evaluation.py` has AUC, log loss, precision@k, NDCG@k,
        MRR and a classification report. Tests gate on:
        - listing search quality (NDCG@3 ≥ 0.9 on judged queries, better than full-text alone)
        - ranker learning and activation
        - a 38-example moderation set (`app/ml/data/moderation_eval.jsonl`): every unsafe or
          doubtful message reaches review, and no safe one is warned by rules alone
        - `python -m app.ml.cli evaluate-moderation --llm` measures rules plus Claude (paid
          calls)
      - **Fixed along the way:** seeded dev accounts couldn't sign in, because their `.test`
        email domain is rejected as reserved. They are now `@seed.example.com`, with a test that
        signs in. The listings and flatmates pages showed "no results" under a loading error.
      - **Checked in the browser:**
        - Listing search and "about me" search on seeded data.
        - A scam message from the other participant arrived live with its warning.
        - Editing that message into harmless text removed the warning live.
        - Suggestion chips fill the composer without sending, on desktop and mobile.
      Not covered:
      - Claude and Voyage were not called live: no keys are set here. The wrapper is tested
        with a fake client.
      - The moderation eval set was written alongside the rules, so its scores are optimistic.
        Measure precision on real reports after launch.
      - The local embedder only matches shared words and word pieces. Paraphrases ("meals"
        vs "food") need Voyage.
      - AI moderation, embedding refresh and ranker training need the worker and beat running
        (item 18a).
      - `POST /search/properties` (not used by the web app) still uses plain text matching.
      - The web lifestyle form saves to `lifestyle_profiles`, but matching, the diet and sleep
        filters and the ranker read `profiles.lifestyle_traits`, which only the older quiz
        endpoint and the seed fill. That pre-dates this item and needs its own fix.
- [x] **11. Payments and subscriptions.** *(Done.)* Razorpay Subscriptions in INR, auto-renewing
      monthly, in `apps/api/app/modules/billing/` (migration `010_billing`). Billing switches on
      only when `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` are all
      set. Until then everything is free and unlimited, and the web app says plans are coming soon.
      - **Plans** (seeded by the migration, prices are placeholders to confirm before launch):
        - **Seeker Pro**, ₹199/month: see who liked you, and unlimited likes (free: 25 a day,
          `FREE_DAILY_LIKES`, reset at midnight IST).
        - **Owner Pro**, ₹499/month: unlimited published listings (free: 2,
          `FREE_ACTIVE_LISTINGS`) and up to 3 featured listings.
        - The matching Razorpay plan is created on first checkout and recreated if the price
          changes (Razorpay plans are immutable).
      - **API:**
        - `GET /billing/plans` (public)
        - `GET /billing/me`: entitlements, usage and subscriptions
        - `POST /billing/subscriptions`: starts checkout and reuses an unpaid one
        - `POST /billing/subscriptions/verify`: checks the Checkout signature, then confirms
          with Razorpay before unlocking anything
        - `POST /billing/subscriptions/{id}/cancel`: stops renewal at the end of the paid
          period
        - `POST /billing/webhooks/razorpay`
      - **Webhooks:**
        - HMAC-SHA256 over the raw body, compared in constant time.
        - Every event is stored in `billing_events` and committed before it is processed, so
          duplicates are skipped and failed events can be retried by Razorpay.
        - Out-of-order events are ignored using the event time.
        - Renewals extend featured listings.
        - Users get an in-app notification when a plan starts, a payment fails, a plan is
          halted, or it is cancelled.
      - **Entitlements:** limits are enforced on the server and the web app only reflects them.
        Over a limit, the API returns `402` problem+json with `error_code` (`UPGRADE_REQUIRED`
        or `FEATURED_LIMIT`), `feature` and `plan`. The web app turns that into an inline
        "See plans" prompt, never a dead end; a listing wizard keeps its draft. A cancelled
        plan keeps working until the paid period ends. Admins bypass the listing cap. Unpaid
        or local subscriptions are expired by the maintenance worker; Razorpay-backed ones
        follow Razorpay's events.
      - **Web:**
        - `/pricing` (linked in the footer): plan cards, "Your plan" with the renewal date,
          and a two-step cancel.
        - "Who liked you" on Matches: a locked count for free users, and for Pro a list with
          Like back (an instant match) and Pass.
        - Feature/Unfeature on the owner portal, and a Featured badge on listing cards.
          Featured listings sort first.
      - **Tests:** `tests/test_billing_db.py` covers:
        - billing off
        - the like cap and the listing cap
        - checkout, plan reuse and signature checks
        - webhook signature, duplicates, stale events, ignored events and halts
        - cancel and expiry
        - featured listings
        - who liked you
        Razorpay itself is faked with an HTTP mock transport. Web helpers are covered in
        `apps/web/tests/billing.test.ts`.
      - **Checked in the browser** (local, dummy keys, Razorpay never called):
        - billing off and billing on
        - the 402 prompt on Feature
        - locked and unlocked who-liked-you
        - Like back creating a match
        - pricing on mobile
      Not covered:
      - No live Razorpay test: there are no test-mode keys here. Before launch:
        - Create test keys and a webhook pointing to `<API_URL>/api/v1/billing/webhooks/razorpay`,
          with the subscription.* events.
        - Run one subscribe, renew and cancel in test mode.
        - Then switch to live keys.
      - Prices, GST and invoices are business decisions: no GST is shown or charged yet.
      - Webhooks are only reprocessed when Razorpay retries. There is no admin replay tool yet.
- [x] **12. Identity verification is mocked.** *(Done: ID checks switched off, email checks
      made real.)* Decision: no KYC provider for launch. Migration `011_email_verification`.
      - **ID documents are off:** the fake flow is removed. It posted a placeholder
        `document_url` and had an approve-only admin endpoint. Pending requests from it were
        cancelled. Badges it granted were cleared, because nothing had been checked. The app
        says ID checks aren't available yet. Adding a provider later means a new `method` on
        `verifications`.
      - **Work and college email by one-time code**
        (`POST /verification/email/send`, `/verification/email/confirm`):
        - Free and disposable mailboxes are refused. College emails need an academic domain
          (`.ac.in`, `.edu`, `.edu.in` and the like).
        - Codes work like phone codes: only an HMAC is stored, compared in constant time, and
          each code allows 5 tries. Codes last 30 minutes (`EMAIL_CODE_TTL_MINUTES`), and a new
          code replaces the old one.
        - Send limits are kept in the database: a cooldown, plus hourly caps per user and per
          address, so nobody can flood someone's inbox.
        - The address is never stored, only its domain and a keyed hash. A partial unique
          index allows one address on one account.
        - A new work email replaces the old one, for someone who changed jobs.
      - **What the badge means now:** `users.is_verified` means "has a verified work or college
        email". Others see a badge, not the domain.
        - Trust score: 30 base, plus 30 for a verified mobile, plus 40 for an email (counted
          once).
        - `is_fully_verified` means both the mobile and an email are verified.
      - **Honest copy:**
        - The public flatmate profile showed "Verified Identity" on everyone (`isVerified={true}`).
          It now uses `is_verified`, which `/profiles/{id}` returns.
        - The account panel's "Email verified" badge (tied to `is_verified`) is gone. Nothing
          verifies the sign-in email.
        - The home, safety, help and privacy pages, the footer and the chat phone-number tip now
          describe what is actually checked.
        - Listing "Verified" badges now say "reviewed by our team", not "ownership and identity
          review".
      - **Seed:** seeded members get a real-looking work-email verification row behind their
        badge.
      - **Tests:** `tests/test_email_verification_db.py` has 20 tests:
        - domain rules
        - the code flow, including that the address isn't stored
        - one address per account
        - replacing a work email
        - cooldown, attempt, expiry and supersede limits, and the per-address hourly cap
        - that ID endpoints are gone and old manual approvals don't count
        Web helpers are covered in `apps/web/tests/verification.test.ts`.
      - **Checked in the browser** (local, in-memory email, no real mail sent):
        - Gmail refused
        - a college code: wrong code refused, right code verified
        - badges on profile and dashboard
        - shield shown and hidden on public profiles
        - mobile layout
      Not covered:
      - Real delivery wasn't tested. Codes go through the configured email provider (`resend`
        or `smtp`), so check one arrives in staging.
      - The academic-domain rule misses colleges that use plain domains (e.g. `.in` or `.com`).
        Those students can't get a college badge yet.
      - The free-provider list is hand-made. Extend it if abuse shows up.
      - The privacy page wording changed, to say what is stored for email checks. Review it
        with the rest of the legal copy.
- [x] **13. Web push and in-app notification centre.** *(Done.)* Migration
      `012_notifications_push`.
      - **What notifies, and where it links:** every notification has a `category` (messages,
        matches, rentals, account) and a same-site `link`. Links must start with a single `/`;
        anything else is dropped.
        - New match: both people, to `/matches`.
        - A like or super-like: "Someone new likes you", with no name (that stays a paid
          feature).
        - Application received (owner) or status changed (applicant, or the owner when it's
          withdrawn): opens the right tab, e.g. `/owner?tab=applications`.
        - Visit requested or changed: the other party, with the time in IST.
        - New chat message: "New message from {first name}". The message text is never
          included, because notifications show on lock screens and go through push services.
        - Billing notices link to `/pricing`.
        - The same event on the same thing is one notification while it's unread. Chat bursts
          collapse into one per chat per 5 minutes, but once it's read the next message
          notifies again.
        - Event hooks run after the main commit and can't break the action that caused them.
      - **In-app centre:**
        - The navbar bell shows a live unread count from the socket's `notification.created`.
          It refetches after reconnects and when the centre changes anything.
        - Its dropdown shows the latest 6. Clicking one marks it read and opens its link, and
          there's "Mark all as read".
        - `/notifications` has All and Unread tabs, groups by day, loads older pages, updates
          live, and stays in step with the bell.
        - API: `GET /notifications/?unread_only&before&limit`, `/unread-count`, `/read-all`,
          `PATCH /{id}/read`.
        - Read rows are purged after 90 days and all rows after 365 days (maintenance task).
      - **Web Push (VAPID, `pywebpush`):**
        - `public/sw.js` shows the push and opens its link, same-site only. `app/manifest.ts`
          makes the app installable, which iPhone and iPad need for push.
        - Settings on `/notifications`: turn push on or off per device, and choose which
          categories may push. Everything still shows in the app.
        - Subscriptions are only accepted for the real push services (Google, Mozilla,
          Microsoft, Apple) over https, with keys of the right length. That blocks using the
          server to call arbitrary URLs. An endpoint moves to whoever subscribed last, and
          signing out removes this browser's subscription.
        - Delivery goes through the outbox (`push.send`), queued in the same commit as the
          notification:
          - gone subscriptions (404/410) are deleted
          - other failures are counted, and a subscription is dropped after 10
          - chat pushes are urgent with a 6-hour TTL; others have a 24-hour TTL
          - no chat push is sent while the person is online, because they see it live
        - Push is off unless `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT` are set.
          Generate a pair with `python -m app.modules.notifications.vapid`.
      - **Tests:** `tests/test_notifications_push_db.py` has 9 tests:
        - link safety and the push-service allowlist
        - paging and read state
        - each event's text and link
        - chat without text, including the burst-then-read rule
        - subscriptions with preferences
        - delivery and cleaning up gone subscriptions
        - skipping online users
        - no VAPID means nothing is queued
        - the purge
        Web helpers are covered in `apps/web/tests/notifications.test.ts`.
      - **Checked in the browser** (local):
        - a chat message arrives live in the bell and the centre
        - clicking opens the chat and marks it read
        - a new message after reading notifies again
        - "Mark all" from the bell updates the centre
        - `?tab=` links open the right dashboard tab
        - mobile layout
      Not covered:
      - A real push wasn't delivered: the app's browser pane blocks notification permission.
        Test on staging in Chrome, Firefox and an installed iPhone app.
      - iPhone and iPad only get push from the Home Screen app (iOS 16.4+). The settings card
        says so.
      - A push that fails for a temporary reason isn't retried; only the failure is counted.
        The notification is still in the app.
      - `/messages` and `/notifications` open a second WebSocket, because the bell has its own.
      - Production needs its own VAPID keys. Changing them later makes every browser
        subscribe again.
- [x] **13b. Admins cannot override application status.** *(Done.)* `PATCH /applications/{id}/status`
      never passed `is_admin`, unlike appointments, so moderators could not intervene.
      Migration `013_application_status_history`.
      - **Who:** staff means moderators, admins and super admins (`is_staff`, which reads roles
        the same way `require_roles` does). Staff acting on someone else's application is an
        override. On their own application they follow the normal rules.
      - **Override rules (one code path, the same PATCH):**
        - A reason (`note`, 5–500 characters) is required.
        - It can't set the current status, or `submitted` (use `under_review` to reopen).
        - A reopen is refused if the applicant already has another active application for that
          listing.
        - Statuses are now a fixed list for everyone, so unknown values get a 422. Before, an
          admin bypass could have stored any string.
        - The row is locked (`FOR UPDATE`), so an owner's decision and an override can't
          interleave.
      - **History:** every status change (owner, applicant or staff) is written to
        `application_status_events`: who, from what, to what, the reason, and whether it was
        staff.
      - **Who is told:** after an override, both the applicant and the owner get "… Updated by
        Flatmate support". The reason stays with staff. The applicant's status email still goes
        out as before.
      - **Admin console:** a new Applications tab (`GET /admin/applications`, staff only):
        - search by listing title or applicant name or email (wildcards are literal)
        - filter by status, and page through results
        - "Change status" opens a dialog with the new status, the required reason and the
          history (`GET /admin/applications/{id}/history`)
      - **Tests:**
        - `tests/test_application_override_db.py` (4 tests): permissions and unknown statuses;
          reason, same-status and no-`submitted` rules; history; what each side is told;
          reopen conflicts; search and access.
        - The mocked admin test in `test_applications_appointments.py` now needs a reason and
          checks the history row.
        - Web helpers are covered in `apps/web/tests/admin-applications.test.ts`.
      - **Checked in the browser** (local, as the seeded admin):
        - search
        - the missing-reason message
        - overriding to Rejected
        - the history in the dialog
        - Priya's notification
        - mobile layout
      Not covered:
      - The admin console page itself still only opens for admins. Moderators can use the API
        and `/admin/moderation`, but not this tab.
      - Owners and applicants don't see the history; only staff do.

## P2 — Operations and hardening

- [x] **14. Browser E2E tests.** *(Done.)* Playwright (`apps/web/e2e`, `playwright.config.ts`).
      Every journey runs twice: `desktop` (1366×900) and `mobile` (Pixel 7). Both use Chromium.
      - **Journeys:**
        - A visitor finds a listing by search, opens it, and is sent to sign-in on "Apply".
        - A wrong password is refused. Priya signs in, sees her space, signs out, and
          `/notifications` asks her to sign in again.
        - A non-admin gets "Access Denied" on `/admin`.
        - A new seeker applies through the listing page. `owner_ravi` accepts from
          `/owner?tab=applications`. The seeker sees it accepted in My Space and in
          notifications.
        - Live chat between two new members:
          - the message reaches the reader's open notification centre over the socket, with no
            reload
          - the bell shows 1 unread
          - the notification doesn't contain the message
          - clicking it opens the chat with the message
        - The API is reachable from the test runner.
      - **Data:** journeys that change data register fresh users, so runs (and both viewports in
        parallel) never collide and the suite can rerun on the same database. The seeded
        password is read from `database/seeds/seed.py` (or `E2E_SEED_PASSWORD`), not copied.
      - **CI:** a new `e2e` job in `ci.yml` runs after the backend and frontend gates:
        - PostGIS with pgvector, plus Redis
        - migrate and seed
        - the API with in-memory email and SMS
        - a production build of the web app
        - Playwright Chromium
        On failure it uploads the report, traces, screenshots and both server logs.
      - **Locally:** start the API and a production build (`next build && next start`), then run
        `pnpm --filter @flatmate/web test:e2e`. Use `E2E_BASE_URL` / `E2E_API_URL` for other
        ports. Against `next dev`, the first visit to each page compiles slowly enough to time
        out redirects.
      - **Checked:** 12/12 passing, twice in a row, against a local production build (about 45
        seconds).
      Not covered:
      - The CI job hasn't run on GitHub yet. Its first run is the real check of the workflow.
      - Only Chromium is tested. Safari/WebKit (iPhone) isn't run.
      - No real push notification and no email delivery; those use in-memory providers.
      - Visual regression and accessibility scans aren't part of the suite.
- [x] **15. Observability.** *(Done; turning it on needs a Sentry project and two repository
      variables.)* Sentry (web + api), structured logs shipped somewhere, uptime checks.
      - **Error tracking (Sentry), off until a DSN is set:**
        - API and worker (`app/core/observability.py`): `SENTRY_DSN`, `APP_RELEASE`,
          `SENTRY_TRACES_SAMPLE_RATE`. Unhandled errors are logged with their traceback and
          reported through the logging integration, tagged with the request ID. Celery tasks
          are covered by the SDK's Celery integration.
        - Web (`@sentry/nextjs`): browser, server render and route-handler errors, plus both
          error boundaries. With no `NEXT_PUBLIC_SENTRY_DSN` at build time, the Next config
          isn't wrapped and the SDK isn't loaded. Source maps upload only when `SENTRY_ORG`,
          `SENTRY_PROJECT` and `SENTRY_AUTH_TOKEN` are set.
        - Privacy, on both sides:
          - no request bodies, cookies, auth headers, query strings, IPs or local variables
          - users by id only
          - tokens, OTPs and passwords redacted from messages and breadcrumbs
          - no session replay
      - **Structured logs:**
        - Outside development and test, the API writes JSON lines in Cloud Logging's format
          (`severity`, `message`, `stack_trace`, and `logging.googleapis.com/trace` when
          `GOOGLE_CLOUD_PROJECT` is set). Cloud Run ships stdout to Cloud Logging, so nothing
          else is needed. `LOG_FORMAT=text|json` overrides it.
        - One root handler, so module loggers, uvicorn and SQL debug output all share the
          format and carry the request ID. Uvicorn's duplicate access log is muted, as are
          httpx's per-call INFO lines.
        - Client `X-Request-ID` values are reused only if they're safe characters (64 at most),
          so log lines can't be forged.
        - Fixed: the Aadhaar redaction pattern was rewriting digits inside UUIDs. It now only
          matches standalone 12-digit numbers.
      - **Readiness is real:** `/health/ready` runs `SELECT 1` (3 s timeout) and returns 503 if
          the database is down. Redis is reported (`ok` / `unavailable` / `error`) but doesn't
          fail readiness, since the app runs without it. The response includes the release and
          isn't cached.
      - **Uptime:** `.github/workflows/uptime.yml` probes `UPTIME_API_URL/health/ready` and
          `UPTIME_WEB_URL` every 10 minutes, with 3 tries each. A failed run is the alert. The
          staging deploy now sets `APP_RELEASE` (the commit) and `GOOGLE_CLOUD_PROJECT`.
      - **CI was red:** mypy had failed on `main` since 990cceb (21 errors: SQLAlchemy row types,
        unchecked `None`s, the WebSocket frame `data`). So pytest and the new e2e job never ran.
        All fixed; mypy is clean.
      - **Tests:** `tests/test_observability.py` (7 tests):
        - JSON lines with request ID, trace and redaction
        - request ID and trace validation
        - the Aadhaar pattern
        - Sentry scrubbing, and Sentry off without a DSN
        - safe request IDs over HTTP
        - readiness 200 and 503
        Web scrubbing is covered in `apps/web/tests/sentry-scrub.test.ts`.
      - **Checked:**
        - the web build with and without a DSN (dummy DSN on a closed local port)
        - no Sentry SDK loaded on pages without a DSN
        - readiness and request IDs against the running API
        - e2e 12/12 against a production build
      Not covered:
      - No event was actually sent to Sentry; that needs a real project. After setting the DSN
        on staging, trigger a test error and check the report has no personal data.
      - Alert rules (in Sentry and Cloud Monitoring) and the `UPTIME_*` variables need setting
        up in those consoles.
      - GitHub's scheduled runs can be late and pause after 60 days without activity. Add a
        Cloud Monitoring uptime check for tighter alerting.
      - Web logs stay in Vercel's log view; they aren't drained anywhere else.
- [x] **16. Security pass: limits, uploads, CSP, group privacy.** Done:
      - **Rate limits** (`app/core/rate_limit.py`):
        - Counts are shared in Redis: a sliding window per key, updated atomically by a Lua script.
          They survive restarts and don't multiply with instances. When Redis is down it falls
          back to per-process counts.
        - Signed-in calls key on the verified user id from the access token. A forged or refresh
          token counts as anonymous.
        - Anonymous calls key on the client IP. `X-Forwarded-For` is trusted only as far as
          `TRUSTED_PROXY_HOPS` proxies vouch for it (0 locally, 1 on Cloud Run, set in the staging
          deploy).
        - 429s carry `Retry-After`, and keys never hold an email.
      - **New limits:**
        - per IP: login, register, refresh, forgot and reset password (generous, because hostels
          and offices share one address)
        - per account (hashed email): login (10 per 15 minutes) and reset emails (5 per hour)
        - chat sends: 30 a minute per user, shared by REST and the socket
        - new conversations: 30 an hour
        - uploads: 100 an hour; chat attachments: 30 per 10 minutes
      - The failed-login log line no longer includes the email.
      - **Uploads:**
        - Files are read in chunks and stop at the bucket limit, instead of being read whole
          first. Upload routes get a 16 MB body cap (it was 10 MB, below the 15 MB document limit).
        - The type comes from the file's bytes when the client sends a generic one. A specific
          declared type that the bytes contradict is still rejected.
        - PDFs with JavaScript, launch actions, embedded files, XFA or forms that submit are
          rejected. Escaped names like `/J#61vaScript` are caught too.
        - More executable headers are rejected.
        - ClamAV scanning (`app/infrastructure/virus_scan.py`, clamd INSTREAM over TCP) runs when
          `CLAMAV_HOST` is set. With `VIRUS_SCAN_REQUIRED`, uploads get a 503 while the scanner is
          missing or down.
      - **Web CSP** (`apps/web/lib/csp.mjs`):
        - It pins script, connect, image and frame sources to the site itself, the API and
          socket origins, Razorpay, the image hosts and Sentry ingest (which also receives CSP
          reports when a DSN is set).
        - It sets `object-src 'none'`, `base-uri 'self'`, `form-action 'self'` and
          `frame-ancestors 'none'`, plus HSTS in production builds. `X-XSS-Protection` is now `0`.
        - `CSP_REPORT_ONLY=true` switches it to report-only.
      - **Groups:**
        - The public list and detail show non-members a member count only: no member ids,
          creator or wishlist votes.
        - Compatibility (member names and pairwise scores) is now members and staff only; any
          signed-in user could read it before.
        - The city filter escapes wildcards, and the list is capped at 200.
      - Also fixed two mypy errors that CI would have flagged.
      - **Tests:** `apps/api/tests/test_security_pass.py` (25) and `apps/web/tests/csp.test.ts`
        (5). The Redis test uses the CI Redis, or fakeredis locally.
      - **Checked:**
        - e2e 12/12 against a production build with the CSP enforced, including the live chat
          socket
        - no CSP violations on the main pages
        - group trimming, the creator's full view, the compatibility 403, upload sniffing and the
          PDF rejection, all against the running API
      Not covered:
      - The Razorpay checkout wasn't opened under the CSP. Do a test payment on staging and
        watch the console.
      - `TRUSTED_PROXY_HOPS=1` assumes Cloud Run with no load balancer in front. Use 2 with an
        external HTTPS load balancer. Check a real request's `X-Forwarded-For` on staging.
      - No ClamAV is deployed yet (e.g. a clamd container on Cloud Run reachable over the VPC);
        that's deploy work under item 18. Until then, keep `VIRUS_SCAN_REQUIRED=false`.
      - The PDF check reads names in the raw file. Content hidden inside compressed object
        streams needs ClamAV (or re-rendering the PDF) to catch.
      - Scripts still allow `'unsafe-inline'` (Next.js inline bootstrap). Nonces would make every
        page dynamic.
- [x] **16b. Account deletion and data export.** Decisions:
      - a 30-day grace period
      - messages kept as "Deleted user"
      - payments kept de-identified
      - listings deleted, with applicants notified
      Done:
      - **Export:** `GET /users/me/export` (5 per hour) returns the person's own records from
        every linked table as JSON. It leaves out password and code hashes, push keys and
        endpoints, internal search/ML columns, and other people's actions about them (who blocked
        or reported them, or applied to their listing).
      - **Deletion request:** `POST /users/me/deletion` needs the password (5 per hour).
        - The account is deactivated at once, so every token stops working and it leaves search
          and matching.
        - Published listings are paused, renewing plans are cancelled (it refuses if that fails,
          so nobody keeps paying), and push subscriptions are removed.
        - An email gives the deletion date and a sign-in link.
      - **Cancelling:**
        - Signing in within 30 days cancels and restores the paused listings; the login page says
          so.
        - Staff deactivation locks a pending deletion, so signing in can't undo it. Staff
          reactivation cancels it.
      - **Erasure** (`purge_due_accounts`, run by the hourly maintenance job, safe to run
        concurrently):
        - Personal records go: profile, lifestyle, verifications, phone codes, roles, privacy
          settings, notifications, push, likes and matches, blocks, reports they filed, their
          applications and viewings, tenancies, group memberships and chat settings.
        - Listings are deleted, and people with open applications or upcoming viewings are
          notified.
        - Groups pass to the longest-standing member.
        - Messages stay, from "Deleted user", and attachments are removed.
        - Payments and subscriptions stay, linked only to the anonymous tombstone row (no email,
          name, phone or usable password).
        - Their files are removed from every bucket.
      - **Web:**
        - A "Your data" card on Profile → Account & security has a download button and a
          deletion dialog that lists what happens and asks for the password.
        - The login page shows the deletion date, and a "welcome back" message after a restore.
        - The old "contact our DPO to delete" line now points there only for corrections and
          other requests.
      - **Schema:** migration `014_account_deletion` (`users.deleted_at` and
        `account_deletion_requests`); `complete_hosted_schema.sql` is regenerated.
      - **Tests:** `apps/api/tests/test_account_privacy_db.py` (6) and
        `apps/web/tests/account-data.test.ts` (4).
      - **Checked in the browser** against the production build:
        - the export's contents
        - the wrong password refused
        - deletion signing out with the dated notice
        - signing back in restoring the account
        - e2e 12/12
      Not covered:
      - Erasure runs only where the worker and beat run. Item 18a deploys them to staging once
        the `STAGING_REDIS_URL` secret exists.
      - An open chat socket isn't closed at once when someone deletes; it drops at its next
        reconnect.
      - Reports filed *about* the deleted person stay, attached to the anonymous row. Decide how
        long moderation keeps them.
      - Outbox rows that already hold their email address (queued mail) are purged by the
        normal outbox retention: 7 days published, 30 days failed.
      - Backups still contain erased data until they expire. Set a backup retention under
        item 18.
      - Storage files are removed by folder prefix. Supabase removal wasn't tried against a real
        project.
      - The wording in the existing "Your data rights (DPDP Act 2023)" card is unchanged and
        should be checked by whoever owns the legal text.
- [x] **17. SEO and performance.** Metadata/OG for property pages, image optimisation,
      Lighthouse of at least 90 on mobile.
      Done:
      - **Listing pages are rendered on the server.**
        - `/properties/[id]` fetches the listing (cached 5 minutes) and sends a title like
          "Sunlit 3BHK Flat in HSR Layout | Flatmate", a description with the rent and area, a
          canonical link, Open Graph and Twitter cards using the first photo, and schema.org
          JSON-LD (Accommodation with a monthly Offer).
        - A missing listing is `noindex`.
        - `/properties` sends the first page of results in the HTML, so filtering starts from
          what is already there.
      - **Site-wide:**
        - Every public section (listings, flatmates, PGs, tenants, groups, pricing, help) has its
          own title, description and canonical link.
        - Signed-in areas (dashboard, messages, profile, owner, admin, sign-in pages and so on)
          are `noindex`.
        - A default 1200×630 link-preview image.
      - **`robots.txt` and `sitemap.xml` are generated.**
        - The sitemap holds the public pages plus every published listing (refreshed hourly).
        - robots.txt blocks everything unless the web app was built with
          `ENVIRONMENT=production`; then it blocks only the private areas and points to the
          sitemap. Staging and local builds stay out of search results.
        - The site origin comes from `NEXT_PUBLIC_APP_URL`.
      - **Images** go through the Next.js optimizer (AVIF/WebP, resized per screen):
        - Unsplash, Supabase storage and the API's `/uploads` are allowed; any other host is
          shown as-is rather than broken.
        - The first card and the gallery's main photo load first; thumbnails load lazily.
      - **Layout shift:**
        - Removed the root loading screen, which flashed before every page and moved the content
          (CLS 0.49 on `/flatmates`).
        - `/groups` shows 12 groups at a time with "Show more" (rendering all 50+ blocked the main
          thread for about 0.9s on a phone).
      - **Measured** on the production build with Playwright, using Lighthouse's mobile settings
        (Pixel 7, 4× CPU slowdown, 1.6 Mbps / 150 ms):

        | Page | LCP before | LCP after | TBT before | TBT after | CLS after |
        |---|---|---|---|---|---|
        | `/` | 1.56s | 1.15–1.33s | 440ms | 230–515ms | 0 |
        | `/properties` | 2.87s | 1.34–1.41s | 414ms | 180–295ms | 0 |
        | listing | 1.46s | 1.03s | 377ms | 193ms | 0 |
        | `/flatmates` | — | 1.8–2.0s | — | 170–260ms | 0.018 (was 0.49) |
        | `/groups` | — | 0.8–0.9s | 850–920ms | 330–630ms | 0 |

        TBT varied run to run with the machine's load. All pages are within Lighthouse's "good"
        range for LCP (under 2.5s) and CLS (under 0.1).
      - **Tests:**
        - `apps/web/tests/seo.test.ts` covers metadata, JSON-LD escaping, robots and site rules,
          image hosts and listing query parsing.
        - Web unit tests 105/105; e2e 12/12.
      Not covered:
      - **Lighthouse itself wasn't run.** Downloading it was blocked in this environment.
        - Run `npx lighthouse <url> --preset=perf --form-factor=mobile` (or PageSpeed Insights)
          against staging to get the actual score.
        - TBT is the risk: 200–500ms here, where Lighthouse wants under 200ms for full marks.
          Most of it is the shared JavaScript every page loads (React, the auth and Supabase
          clients, Sentry).
      - **Production settings:**
        - Set `NEXT_PUBLIC_APP_URL` to the real domain, and `ENVIRONMENT=production` when
          building the production web app. Without them, canonical links point to localhost and
          the site isn't indexed.
        - `API_INTERNAL_URL` is optional (a private API address for server rendering).
      - **Freshness:** a changed or unpublished listing can take up to 5 minutes to update in
        search previews and the page's first HTML.
      - **Unchanged pages:** `/flatmates`, `/pg` and `/groups` still load their data in the
        browser. They show sign-in or personal results, so there's little to index.
- [x] **18a. Deploy the worker and beat.** The staging workflow deploys only the API. Without a
      worker, emails still go out immediately (the in-request kick), but retries happen only when a
      later request triggers a dispatch, and maintenance never runs. Deploy one worker and exactly
      one beat (e.g. a Cloud Run service with always-on CPU, or Cloud Scheduler calling a Cloud
      Run job), plus a managed Redis.
      Done:
      - **Worker entrypoint** `python -m app.workers.run` (`apps/api/app/workers/run.py`):
        - Runs the Celery worker with beat inside it.
        - Serves `/health` on `$PORT`. It returns 503 until Celery has reached Redis and is
          taking tasks, 200 while it runs, and 503 once Celery stops; the process then exits so
          the host restarts it.
        - Passes SIGTERM to Celery for a warm shutdown. Tasks are acked late, so one cut off
          is delivered again.
        - Settings: `WORKER_EMBED_BEAT`, `WORKER_CONCURRENCY`, `WORKER_POOL`.
      - **Managed Redis over TLS:** `rediss://` URLs now work for the Celery broker and backend.
        Certificates are verified unless the URL says otherwise; before, Celery refused such
        URLs.
      - **Staging workflow:**
        - Redis is one Secret Manager secret, `STAGING_REDIS_URL`. The API gets it too, for
          shared rate limits, its cache and chat across instances.
        - When the secret exists, the workflow deploys `flatmate-worker-staging` from the same
          image with the same settings:
          - one instance (min = max = 1), so exactly one beat
          - CPU always on
          - internal ingress, no public access
          - a startup probe, so a worker that can't reach Redis fails the deploy instead of
            going live idle
          - a liveness probe
        - Until the secret exists, the workflow warns and skips the worker instead of failing.
        - Optional `STAGING_VPC_NETWORK` / `STAGING_VPC_SUBNET` variables are for a Redis on a
          private network (Memorystore).
      - **Other deploy files:**
        - `docker-compose.prod.yml` gains a worker and a single beat.
        - Its default Redis URLs now carry `REDIS_PASSWORD`. The bundled Redis requires it,
          so before this the API couldn't connect.
        - `infrastructure/deployment/k8s-deployment.yaml` gains a one-replica worker with the
          `Recreate` strategy, so there's never a second beat.
      - **Runbook:** `DEPLOYMENT.md` step 5 covers creating the Redis and the secret, and
        checking the worker.
      - **Tests:** `apps/api/tests/test_worker_runtime.py` (5).
        - It covers the command line, health states and TLS options.
        - It also starts the real entrypoint and waits for it to report ready. On Linux (CI) it
          runs with beat embedded and checks for a clean shutdown on SIGTERM.
      Not covered:
      - **Not deployed:** nothing has been run against GCP from here.
        - Before the first run, create the Redis and the `STAGING_REDIS_URL` secret, and give the
          Cloud Run runtime service account access to it.
        - The worker's `--startup-probe` / `--liveness-probe` flags need a recent gcloud (the
          runner's preinstalled one is).
      - **Untested locally:**
        - Beat embedded in the worker, and Celery against a real Redis. This machine has no
          Redis and Docker wasn't running; the test used Celery's in-memory broker.
        - The workflow has no actionlint run (blocked earlier); it was only checked as valid
          YAML.
      - **Cost:** one always-on Cloud Run instance (1 vCPU, 1 GiB) plus the Redis.
      - **Statement timeout:** the app database role's 15-second statement timeout applies to
        the worker too. Large maintenance or retraining queries may need a longer one later.
      - **Deploy overlap:** a rolling deploy can briefly run two beats. Every scheduled job is
        safe to overlap (rows are claimed with `SKIP LOCKED`), so the worst case is an extra
        sweep.
- [x] **18. Production deploy pipeline.** The staging workflow exists, but production promotion,
      backups and a tested restore do not.
      Decided:
      - Production gets an exact staging build, promoted by hand.
      - Backups are kept 30 days.
      Done:
      - **Production Deployment workflow** (`.github/workflows/production-deploy.yml`, run by
        hand with a commit SHA):
        - **Gate job:** the commit must be on `main`, and a staging run must have deployed it
          with a passing readiness check. This runs before anyone is asked to approve.
        - **Release job** (GitHub `production` environment, so required reviewers apply), in
          order:
          - It checks that every production secret is present.
          - It finds the image staging built for that commit. Nothing is rebuilt.
          - It takes a verified backup, then runs migrations.
          - It deploys the API and checks `/health/ready` reports the new release.
          - It deploys the worker, then the web app on Vercel (`--prod`).
        - The run summary gives the exact rollback commands for the previous revisions.
      - **One deploy path for staging and production** (`.github/actions/deploy-cloud-run`):
        - `scripts/deploy_runtime.py` builds the configuration.
        - Every known secret that exists in Secret Manager (`<ENV>_<NAME>`) is passed. A missing
          `APP_DATABASE_URL` or `SECRET_KEY` stops the deploy; production also requires Redis.
        - Plain settings come from the `RUNTIME_ENV` variable, written to a YAML file so values
          can contain commas. Secret names are refused there.
        - Before this, staging received only three secrets, so emails, SMS and storage couldn't
          work there.
      - **Daily verified backups** (`.github/workflows/db-backup.yml`, 03:00 IST;
        `scripts/db_backup.py`):
        - The dump and a manifest come from one database snapshot. The manifest holds the
          Alembic revision, every table's row count, RLS tables and policy count, the extensions
          and roles the schema needs, and the SHA-256.
        - Each backup is restored into a throwaway PostGIS + pgvector container and must match
          its manifest before it's uploaded to Cloud Storage. A failure fails the run.
        - Retention is 30 days, by a bucket lifecycle rule
          (`infrastructure/backup/gcs-lifecycle.json`).
        - The writer accounts can only create objects, so they can't read, replace or delete
          backups.
        - The nightly job uses its own `production-backups` environment, so it never waits for a
          reviewer.
      - **Restore** (`db_backup.py restore`):
        - It only restores into an empty database whose name you confirm, never over live data.
        - It creates the needed extensions (in their own schema, as on Supabase) and roles, and
          restores in one transaction.
        - It fails unless revision, row counts and RLS all match.
        - `DEPLOYMENT.md` §4.4 is the disaster-recovery runbook.
      - **Fixes:**
        - The manual migration workflow used the staging secret name for production; it now
          uses `PRODUCTION_DATABASE_URL`.
        - CI now installs the PostgreSQL 17 client, so the restore test runs there.
      - **Tested locally:**
        - The test database (51 tables, 9,985 rows) was backed up and restored into a scratch
          database and matched its manifest, RLS on all 51 tables included.
        - Restoring into a non-empty database, or one whose name doesn't match, is refused.
        - A truncated dump is caught by its checksum.
        - A Supabase-style layout restores. Extensions live in an `extensions` schema; an
          installed but unused extension is left out of the manifest, and the ones found through
          column defaults and index operator classes are kept.
        - Tests: `apps/api/tests/test_db_backup.py` (5) and `test_deploy_runtime.py` (4).
      Not covered:
      - **Nothing has run on GitHub or GCP.** Before the first production release, set up what
        `DEPLOYMENT.md` §4.1 and §4.3 list: Secret Manager secrets, the GitHub `production` and
        `production-backups` environments, the bucket, the Vercel production settings. Then run
        **Database Backup** by hand once.
      - **The workflows are only checked as valid YAML.** actionlint was blocked here.
      - **Restoring into a hosted Supabase database wasn't tried.** There the restoring user
        isn't a superuser, and default-privilege entries for Supabase's own roles may need
        skipping.
      - **Point-in-time recovery:**
        - Backups are daily plus one before each release, so up to a day of writes can be lost.
        - For less, enable Supabase's point-in-time recovery (paid add-on).
      - **Uploaded files** (Supabase Storage) aren't in these backups.
      - **No automatic rollback.** Rollback is a command from the run summary, and migrations
        must stay compatible with the previous release (add first, remove later).
      - **One GCP project assumed.** Production is assumed to share staging's Artifact
        Registry; for a separate project, set `RELEASE_IMAGE_REPOSITORY` and grant read access.
