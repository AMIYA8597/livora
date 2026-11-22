# Production Launch Gap List

Collected 2026-11-22 from the actual source code (not the phase reports).
Work these top to bottom. Mark each `[x]` only when code + tests land.

## P0 — Blocks launch

- [ ] **1. Hosted Supabase project is unreachable.** On 2026-11-22,
      `qjwitdovbsfviaepjcul.supabase.co` returned NXDOMAIN and the pooler (port 6543, now
      reachable from this network) answered "tenant/user not found". The project is paused or
      deleted. The owner must restore it or create a new one, update the `.env` files, then run
      `database/migrations/complete_hosted_schema.sql` or the `hosted-db-migration.yml` workflow.
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
- [ ] **3b. PostGIS is faked when missing.** Migration 001 creates a stub `st_asewkb` that returns
      one hardcoded point, so all properties get the same location. Remove the fake, require
      PostGIS (Supabase has it), and install it locally.
- [ ] **4. No transactional email.** Nothing sends mail. Needed for verification, password reset
      confirmation, application and appointment notices (Resend/SES adapter + templates).
- [ ] **5. Workers are stubs.** `workers/tasks.py` only uses `print` and `sleep`. Needs real
      tasks: match precompute, notifications/email fan-out, image processing, cleanup jobs.
- [ ] **6. Next.js 14.2.4 has 41 security advisories.** Upgrade to a patched 14.2.x or to 15.

- [x] **2b. Test suite ran against the hosted DB and storage.** `tests/conftest.py` now forces a
      local `flatmate_test` DB plus local storage, and refuses non-local hosts. Result: 136/136
      passing (previously 133 passed, 3 failed).
- [x] **2c. Storage silently fakes success.** *(Done: raises `StorageConfigurationError`; tests in `test_storage_config.py`.)* If the Supabase client fails to initialise,
      `SupabaseStorageProvider` returns `mock.supabase.co` URLs instead of failing. It must raise
      outside dev/test.

- [x] **2d. CI would have failed.** There were 12 existing mypy errors in messaging (the README
      claimed 0). Fixed. CI now passes `TEST_DATABASE_URL`, installs pgvector, and checks the
      migration downgrade/upgrade round-trip.
- [x] **2e. Chat showed the oldest messages.** `get_messages` sorted ascending before applying
      LIMIT, so long chats never showed new messages. It now returns the latest page in
      chronological order (`test_messaging_pagination_db.py`).

## P1 — Required for a quality product

- [ ] **7. Frontend architecture.** 30 pages but only 8 components, and the largest pages are
      about 1,000 lines (`dashboard`, `profile`, `properties/[id]`). Split them into feature
      components, add a shared layout/shell, and handle loading, error and empty states.
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

## P2 — Operations and hardening

- [ ] **14. Browser E2E tests.** No Playwright. Add core journeys on mobile and desktop
      viewports in CI.
- [ ] **15. Observability.** Sentry (web + api), structured logs shipped somewhere, uptime checks.
- [ ] **16. Security pass.** CSP headers on the web app, rate limits on auth/chat/upload, file
      type sniffing and virus scan on uploads, account deletion/export (DPDP Act compliance).
- [ ] **17. SEO and performance.** Metadata/OG for property pages, image optimisation,
      Lighthouse of at least 90 on mobile.
- [ ] **18. Production deploy pipeline.** The staging workflow exists, but production promotion,
      backups and a tested restore do not.
