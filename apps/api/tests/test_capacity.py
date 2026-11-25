"""
Capacity and overload behaviour (docs/CAPACITY_PLAN.md):
  * overload answers 503 + Retry-After at once, never hangs or 500s; health checks still answer;
  * slow requests are stopped with 504; busy-database errors become 503;
  * password hashing runs off the event loop;
  * the hot cache coalesces concurrent misses and never fails a request;
  * traffic numbers (admin Traffic tab, /metrics) add up correctly.
"""
import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import exc as sa_exc

from app.core import hot_cache
from app.core.config import settings
from app.core.metrics import Metrics, metrics, percentile, render_prometheus, summarize
from app.core.overload import OverloadGuard, is_busy_error
from app.core.security import get_password_hash, verify_password_async

API = settings.API_V1_PREFIX


@pytest.fixture(autouse=True)
def fresh_metrics():
    metrics.reset()
    yield
    metrics.reset()


def _client(asgi):
    return AsyncClient(transport=ASGITransport(app=asgi), base_url="http://test")


# ---------------------------------------------------------------- load shedding and deadlines

def _slow_app(release: asyncio.Event, started: list):
    async def asgi(scope, receive, send):
        started.append(scope["path"])
        await release.wait()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
    return asgi


async def test_full_process_answers_503_with_retry_after(monkeypatch):
    monkeypatch.setattr(settings, "MAX_IN_FLIGHT_REQUESTS", 2)
    release, started = asyncio.Event(), []
    guard = OverloadGuard(_slow_app(release, started))
    async with _client(guard) as client:
        held = [asyncio.create_task(client.get("/api/v1/x")) for _ in range(2)]
        while len(started) < 2:
            await asyncio.sleep(0.01)

        t0 = time.perf_counter()
        refused = await client.get("/api/v1/x")
        assert time.perf_counter() - t0 < 1  # refused at once, not queued
        assert refused.status_code == 503
        assert 2 <= int(refused.headers["retry-after"]) <= 4
        assert refused.headers["content-type"] == "application/problem+json"
        assert refused.json()["error_code"] == "SERVER_BUSY"

        # Health checks are never refused, even when full.
        release_health = asyncio.Event()
        release_health.set()
        assert len(started) == 2
        health = OverloadGuard(_slow_app(release_health, []))
        health_client = _client(health)
        metrics.in_flight = 5  # pretend the process is full
        assert (await health_client.get("/health/live")).status_code == 200
        metrics.in_flight = 2
        await health_client.aclose()

        release.set()
        assert [r.status_code for r in await asyncio.gather(*held)] == [200, 200]
    assert metrics.shed_total == 1 and metrics.in_flight == 0


async def test_slow_request_gets_504_and_frees_its_slot(monkeypatch):
    monkeypatch.setattr(settings, "REQUEST_TIMEOUT_SECONDS", 0.2)
    never = asyncio.Event()
    guard = OverloadGuard(_slow_app(never, []))
    async with _client(guard) as client:
        res = await client.get("/api/v1/slow")
    assert res.status_code == 504 and res.json()["error_code"] == "REQUEST_TIMEOUT"
    assert metrics.timeouts_total == 1 and metrics.in_flight == 0


async def test_uploads_have_no_deadline(monkeypatch):
    monkeypatch.setattr(settings, "REQUEST_TIMEOUT_SECONDS", 0.05)
    release, started = asyncio.Event(), []
    guard = OverloadGuard(_slow_app(release, started))
    async with _client(guard) as client:
        task = asyncio.create_task(client.post("/api/v1/storage/upload"))
        await asyncio.sleep(0.2)
        release.set()
        assert (await task).status_code == 200


async def test_apps_own_timeout_error_is_not_mistaken_for_the_deadline():
    async def raises(scope, receive, send):
        raise TimeoutError("provider timed out")

    with pytest.raises(TimeoutError):
        await OverloadGuard(raises)({"type": "http", "path": "/api/v1/x", "method": "GET"}, None, None)
    assert metrics.timeouts_total == 0


def test_busy_database_errors_are_recognised():
    assert is_busy_error(sa_exc.TimeoutError("QueuePool limit of size 10 overflow 20 reached"))

    class TooManyConnectionsError(Exception):
        sqlstate = "53300"

    wrapped = sa_exc.OperationalError("connect", {}, TooManyConnectionsError("sorry, too many clients"))
    assert is_busy_error(wrapped)

    class QueryCanceled(Exception):
        sqlstate = "57014"  # statement_timeout

    assert is_busy_error(sa_exc.DBAPIError("select", {}, QueryCanceled()))
    assert not is_busy_error(ValueError("a bug"))
    assert not is_busy_error(sa_exc.IntegrityError("insert", {}, Exception("duplicate key")))


async def test_pool_exhaustion_becomes_503_not_500(async_client, monkeypatch):
    from app.modules.locations import service as locations

    async def exhausted(self, active_only):
        raise sa_exc.TimeoutError("QueuePool limit of size 10 overflow 20 reached, connection timed out")

    monkeypatch.setattr(locations.LocationService, "_load_cities", exhausted)
    res = await async_client.get(f"{API}/locations/cities")
    assert res.status_code == 503
    assert res.json()["error_code"] == "SERVICE_BUSY"
    assert int(res.headers["retry-after"]) >= 2
    assert res.headers["x-request-id"]
    assert metrics.unavailable_total == 1


async def test_real_requests_are_measured_by_route_template(async_client):
    res = await async_client.get(f"{API}/locations/states")
    assert res.status_code == 200
    await async_client.get(f"{API}/properties/00000000-0000-0000-0000-000000000000")
    routes = metrics.window()["routes"]
    assert routes[f"{API}/locations/states"]["2xx"] == 1
    # The template, never the raw ID.
    assert routes[f"{API}/properties/{{property_id}}"]["4xx"] == 1
    assert not any("00000000" in r for r in routes)


# ---------------------------------------------------------------- passwords off the event loop

async def test_password_checks_do_not_block_other_requests():
    hashed = get_password_hash("correct horse battery staple")
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    task = asyncio.create_task(ticker())
    t0 = time.perf_counter()
    results = await asyncio.gather(*[verify_password_async("correct horse battery staple", hashed) for _ in range(4)])
    elapsed = time.perf_counter() - t0
    task.cancel()
    assert results == [True] * 4
    # The loop kept running while the hashes were checked (bcrypt ~0.2 s each).
    assert ticks >= elapsed / 0.01 * 0.5
    assert await verify_password_async("wrong", hashed) is False


# ---------------------------------------------------------------- hot cache

async def test_concurrent_misses_load_once():
    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return {"n": calls}

    values = await asyncio.gather(*[hot_cache.cached("k", 60, load) for _ in range(50)])
    assert calls == 1 and all(v == {"n": 1} for v in values)
    assert await hot_cache.cached("k", 60, load) == {"n": 1}


async def test_expired_entries_reload_and_errors_are_not_cached():
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("database hiccup")
        return calls

    with pytest.raises(RuntimeError):
        await hot_cache.cached("e", 60, flaky)
    assert await hot_cache.cached("e", 0.05, flaky) == 2
    await asyncio.sleep(0.1)
    assert await hot_cache.cached("e", 60, flaky) == 3


async def test_a_cancelled_loader_does_not_fail_the_waiters():
    gate = asyncio.Event()

    async def slow():
        await gate.wait()
        return "value"

    leader = asyncio.create_task(hot_cache.cached("c", 60, slow))
    await asyncio.sleep(0.01)
    waiter = asyncio.create_task(hot_cache.cached("c", 60, slow))
    await asyncio.sleep(0.01)
    leader.cancel()  # the first client went away
    await asyncio.sleep(0.01)
    gate.set()
    assert await waiter == "value"


async def test_redis_outage_never_fails_a_read(monkeypatch):
    from app.infrastructure import cache

    class Broken:
        async def get(self, *a, **k):
            raise ConnectionError("redis down")

        async def set(self, *a, **k):
            raise ConnectionError("redis down")

    monkeypatch.setattr(cache, "redis_client", Broken())

    async def load():
        return [1, 2, 3]

    assert await hot_cache.cached("r", 60, load) == [1, 2, 3]


def test_cache_keys_are_stable_and_skip_unset_values():
    a = hot_cache.key_for("p", city="Pune", limit=20, q=None)
    b = hot_cache.key_for("p", limit=20, city="Pune")
    assert a == b == "p?city=Pune&limit=20"


async def test_anonymous_listing_pages_are_cached_briefly(async_client, monkeypatch):
    from app.modules.properties import service as properties

    calls = 0
    original = properties.PropertyService.list_properties

    async def counting(self, **kwargs):
        nonlocal calls
        calls += 1
        return await original(self, **kwargs)

    monkeypatch.setattr(properties.PropertyService, "list_properties", counting)
    for _ in range(3):
        assert (await async_client.get(f"{API}/properties/", params={"city": "Pune"})).status_code == 200
    assert calls == 1
    # Different filters are different pages; "near me" is never cached.
    await async_client.get(f"{API}/properties/", params={"city": "Mumbai"})
    await async_client.get(f"{API}/properties/", params={"near_lat": 18.5, "near_lng": 73.8})
    await async_client.get(f"{API}/properties/", params={"near_lat": 18.5, "near_lng": 73.8})
    assert calls == 4

    # The anonymous "recommended" order (the browse page's server render) is shared...
    for _ in range(2):
        assert (await async_client.get(f"{API}/properties/", params={"sort": "recommended"})).status_code == 200
    assert calls == 5

    # ...but a signed-in viewer's ranking is theirs alone, every time.
    from uuid import uuid4

    from sqlalchemy import delete

    from app.core.database import AsyncSessionLocal
    from app.core.security import create_access_token
    from app.modules.users.models import User

    uid = uuid4()
    async with AsyncSessionLocal() as s:
        s.add(User(id=uid, email=f"cache-{uid.hex[:8]}@example.com", hashed_password="x",
                   full_name="Cache Viewer", role="seeker"))
        await s.commit()
    headers = {"Authorization": f"Bearer {create_access_token(subject=str(uid), roles=['seeker'])}"}
    try:
        for _ in range(2):
            res = await async_client.get(f"{API}/properties/", params={"sort": "recommended"}, headers=headers)
            assert res.status_code == 200
        assert calls == 7
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()


# ---------------------------------------------------------------- traffic numbers

def test_percentiles_come_from_the_histogram():
    m = Metrics()
    for _ in range(90):
        m.observe("GET", "/a", 200, 0.02)   # 10-25 ms bucket
    for _ in range(10):
        m.observe("GET", "/a", 500, 0.8)    # 500 ms - 1 s bucket
    hist = m.window()["routes"]["/a"]["hist"]
    assert 10 <= percentile(hist, 0.5) <= 25
    assert 500 <= percentile(hist, 0.95) <= 1000
    assert percentile([0] * 13, 0.5) is None


def test_fleet_summary_adds_instances_up():
    a, b = Metrics(), Metrics()
    for _ in range(60):
        a.observe("GET", "/a", 200, 0.01)
    for _ in range(54):
        b.observe("GET", "/a", 200, 0.01)
    for _ in range(6):
        b.observe("POST", "/b", 503, 0.01)
    b.shed()
    wa, wb = a.window(), b.window()
    wa["instance"], wb["instance"] = "a", "b"
    snap = summarize([wa, wb], "all_instances")
    assert snap["instances"] == 2 and snap["requests"] == 120
    assert snap["requests_per_second"] == 2.0
    assert snap["status"]["5xx"] == 6 and snap["error_rate"] == 0.05
    assert snap["shed"] == 1
    assert snap["routes"][0] == {"route": "/a", "requests": 114, "errors": 0, "p95_ms": snap["routes"][0]["p95_ms"]}
    assert [i["instance"] for i in snap["per_instance"]] == ["a", "b"]


def test_old_slots_drop_out_of_the_last_minute():
    m = Metrics()
    now = time.time()
    m._slot(now - 120).routes["/old"] = {"count": 5, "2xx": 5, "3xx": 0, "4xx": 0, "5xx": 0, "hist": [5] + [0] * 12}
    m.observe("GET", "/new", 200, 0.01)
    assert set(m.window(now)["routes"]) == {"/new"}


def test_route_series_are_bounded(monkeypatch):
    from app.core import metrics as metrics_mod

    monkeypatch.setattr(metrics_mod, "MAX_ROUTES", 3)
    m = Metrics()
    for i in range(10):
        m.observe("GET", f"/r{i}", 200, 0.01)
    assert len(m.window()["routes"]) == 4  # three named + "(other)"
    assert metrics_mod.OTHER_ROUTE in m.window()["routes"]


async def test_metrics_endpoint_needs_its_token(async_client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")
    assert (await async_client.get("/metrics")).status_code == 404
    monkeypatch.setattr(settings, "METRICS_TOKEN", "t" * 32)
    assert (await async_client.get("/metrics")).status_code == 401
    assert (await async_client.get("/metrics", headers={"Authorization": "Bearer wrong"})).status_code == 401
    await async_client.get(f"{API}/locations/states")
    res = await async_client.get("/metrics", headers={"Authorization": f"Bearer {'t' * 32}"})
    assert res.status_code == 200
    assert f'flatmate_http_requests_total{{method="GET",route="{API}/locations/states",status="2xx"}} 1' in res.text
    assert "flatmate_http_request_duration_seconds_bucket" in res.text
    assert "flatmate_http_in_flight_requests" in res.text


def test_prometheus_text_escapes_labels():
    m = metrics
    m.observe("GET", '/we"ird', 200, 0.01)
    assert 'route="/we\\"ird"' in render_prometheus()


async def test_admin_traffic_is_admin_only(async_client):
    from uuid import uuid4

    from sqlalchemy import delete

    from app.core.database import AsyncSessionLocal
    from app.core.security import create_access_token
    from app.modules.users.models import User, UserRole

    seeker, moderator, admin = uuid4(), uuid4(), uuid4()
    tag = uuid4().hex[:8]
    async with AsyncSessionLocal() as s:
        for name, uid in (("seeker", seeker), ("moderator", moderator), ("admin", admin)):
            s.add(User(id=uid, email=f"traffic-{tag}-{name}@example.com", hashed_password="x",
                       full_name=f"{name.title()} Person", role="seeker"))
        await s.flush()
        s.add(UserRole(user_id=moderator, role="moderator", is_verified=True))
        s.add(UserRole(user_id=admin, role="admin", is_verified=True))
        await s.commit()

    def auth(uid):
        return {"Authorization": f"Bearer {create_access_token(subject=str(uid), roles=['seeker'])}"}

    try:
        assert (await async_client.get(f"{API}/admin/traffic")).status_code == 401
        assert (await async_client.get(f"{API}/admin/traffic", headers=auth(seeker))).status_code == 403
        assert (await async_client.get(f"{API}/admin/traffic", headers=auth(moderator))).status_code == 403
        await async_client.get(f"{API}/locations/states")
        res = await async_client.get(f"{API}/admin/traffic", headers=auth(admin))
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["scope"] == "this_instance"  # no Redis in tests
        assert body["instances"] == 1 and body["requests"] >= 4
        assert body["status"]["2xx"] >= 1 and body["status"]["4xx"] >= 3
        assert body["window_seconds"] == 60
        assert any(r["route"] == f"{API}/locations/states" for r in body["routes"])
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(User).where(User.id.in_([seeker, moderator, admin])))
            await s.commit()


async def test_event_loop_lag_is_measured():
    from app.core.metrics import watch_loop_lag

    task = asyncio.create_task(watch_loop_lag())
    await asyncio.sleep(0.05)
    time.sleep(0.6)  # block the loop, as CPU-bound work in a request would
    await asyncio.sleep(0.6)
    task.cancel()
    assert metrics.loop_lag_max_ms >= 50
    assert summarize([metrics.window()], "this_instance")["loop_lag_ms"] >= 50
    assert "flatmate_event_loop_lag_ms" in render_prometheus()
