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

- [ ] **14. Browser E2E tests.** No Playwright. Add core journeys on mobile and desktop
      viewports in CI.
- [ ] **15. Observability.** Sentry (web + api), structured logs shipped somewhere, uptime checks.
- [ ] **16. Security pass.** CSP headers on the web app, rate limits on auth/chat/upload, file
      type sniffing and virus scan on uploads, account deletion/export (DPDP Act compliance).
      Note: `RateLimiter` (`app/core/rate_limit.py`) is in-memory per process, so limits reset on
      restart and multiply with instances. It keys signed-in calls on the token's last 16
      characters (a fresh token resets the limit) and anonymous calls on a client-supplied
      `X-Forwarded-For` (spoofable). Move it to Redis, key on the verified user id, and trust
      forwarded headers only from the platform proxy. (OTP send limits already live in the DB.)
      Also: the public `GET /groups` response includes members' user IDs; trim it to counts for
      anyone who isn't a member.
- [ ] **17. SEO and performance.** Metadata/OG for property pages, image optimisation,
      Lighthouse of at least 90 on mobile.
- [ ] **18a. Deploy the worker and beat.** The staging workflow deploys only the API. Without a
      worker, emails still go out immediately (the in-request kick), but retries happen only when a
      later request triggers a dispatch, and maintenance never runs. Deploy one worker and exactly
      one beat (e.g. a Cloud Run service with always-on CPU, or Cloud Scheduler calling a Cloud
      Run job), plus a managed Redis.
- [ ] **18. Production deploy pipeline.** The staging workflow exists, but production promotion,
      backups and a tested restore do not.
