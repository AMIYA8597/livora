# Load tests

Real user journeys against a running API, to measure capacity and to check that overload
degrades gracefully. The sizing they inform is in [docs/CAPACITY_PLAN.md](../docs/CAPACITY_PLAN.md).

| File | What it does |
|---|---|
| `seed_load.py` | Creates members, owners and published listings across the catalogue cities, and writes `.tokens.json` (git-ignored). `--cleanup` removes them. Refuses non-local databases unless you pass `--allow-host` (staging only; a host that looks like production is refused). |
| `locustfile.py` | The HTTP mix. **Visitors** browse (the browse page, city pages with filters, text search, listing pages). **Members** are signed in (unread count, notifications, chats, recommendations, profile). One **SignIn** user does real sign-ins, paced under the per-IP limit. Exits 1 when failures pass `MAX_FAIL_RATIO` (1%) or p95 passes `MAX_P95_MS` (800). |
| `sockets.py` | Holds N signed-in WebSockets like browser tabs (auth frame, ping every 25 s). Reports connected, failed and dropped sockets, and handshake and pong times. |

## Run it locally

Never against the hosted database: `apps/api/.env` points there. Use a local database, and
start the API with the same `SECRET_KEY` that `seed_load.py` used.

1. **Create and migrate a local database:**

   ```
   createdb flatmate_load && psql -d flatmate_load -c "CREATE EXTENSION postgis"
   DATABASE_URL=postgresql+asyncpg://<user>:<pw>@localhost:5432/flatmate_load alembic upgrade head   # from apps/api
   ```
2. **Seed it, from apps/api with the same DATABASE_URL and a SECRET_KEY:**

   ```
   python ../../loadtests/seed_load.py --members 2000 --owners 300 --listings 3000
   ```
3. **Start the API like production:**

   ```
   DEBUG=False LOG_FORMAT=json uvicorn app.main:app --port 8000 --timeout-keep-alive 75
   ```
4. **Load it.** Use `127.0.0.1`, not `localhost`: on Windows `localhost` tries IPv6 first and
   adds about 2 s to every new connection.

   ```
   locust -f loadtests/locustfile.py --host http://127.0.0.1:8000 --headless -u 700 -r 35 -t 3m --csv loadtests/results/run
   python loadtests/sockets.py --url ws://127.0.0.1:8000/api/v1/messaging/ws --sockets 2000 --ramp 200 --hold 120
   ```
5. **Watch the server while it runs.** Set `METRICS_TOKEN` and read `/metrics`, or open the
   admin console's Traffic tab:
   - `flatmate_event_loop_lag_ms` is the CPU saturation signal;
   - `flatmate_db_pool_checked_out` is the pool;
   - `flatmate_http_shed_total` counts requests turned away.

## Profiles

| Profile | Command | Pass when |
|---|---|---|
| Smoke | `-u 50 -r 10 -t 1m` | 0 failures |
| Steady (one process) | `-u 700 -r 35 -t 3m` | under 1% failed, p95 under 800 ms |
| Overload (one process) | `-u 3000 -r 200 -t 2m`, with `MAX_FAIL_RATIO=1 MAX_P95_MS=100000` | failures are quick 503s with Retry-After; no 500s in the log; the API answers normally right after |
| Launch rehearsal (staging) | distributed, `-u 10000 -r 50 -t 30m`, plus `sockets.py --sockets 10000` | see docs/CAPACITY_PLAN.md section 7 |

Locust's single process tops out at about 1,500 users. For more, run it distributed:
`--master` on one machine and `--worker --master-host <ip>` on others.

## Results so far

See docs/CAPACITY_PLAN.md section 3. In short, one API process (1 CPU, Windows):
- **700 users:** 109 requests a second with 0 failures and p95 260 ms.
- **4× that load:** it turns the excess away with quick 503s, has no 500s and no crash, and
  recovers at once.
- **Sockets:** it holds 5,000 with none dropped.
