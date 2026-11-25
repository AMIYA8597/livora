"""
Flatmate load test: the journeys real people take, in launch-day proportions.

    locust -f loadtests/locustfile.py --host http://localhost:8000          # web UI on :8089
    locust -f loadtests/locustfile.py --host https://staging-api... --headless \
        -u 10000 -r 50 -t 30m --csv results/launch               # the 10,000-user run

Users (weights are the share of virtual users):
  Visitor (6)  anonymous browsing: the browse page, city pages with filters and sorts, free-text search,
               listing pages, the search endpoint, app config.
  Member (3)   signed in (tokens from seed_load.py): who-am-I, unread count, notifications,
               conversations, recommended listings, flatmate matches, profile, listing pages.
  SignIn (1 fixed user) real password sign-ins, paced under the per-IP sign-in limit.

Think time is 3-10 s between actions (people read pages); 10,000 users is then ~1,500 requests a
second. Pass/fail at the end (exit code 1 on fail), overridable with environment variables:
  MAX_FAIL_RATIO (default 0.01)  any non-2xx except expected 404s counts, 503s included
  MAX_P95_MS     (default 800)   over every request
Run sockets.py alongside for the realtime connections signed-in tabs hold.
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

from locust import HttpUser, between, constant_pacing, events, task

API = os.environ.get("API_PREFIX", "/api/v1")
TOKENS_FILE = Path(os.environ.get("TOKENS_FILE", Path(__file__).with_name(".tokens.json")))
DATA = json.loads(TOKENS_FILE.read_text(encoding="utf-8")) if TOKENS_FILE.exists() else {}
CITIES = DATA.get("cities") or ["Bengaluru", "Mumbai", "New Delhi", "Pune", "Hyderabad", "Chennai"]
MEMBERS = DATA.get("members") or []
QUERIES = ["quiet furnished room", "pg near metro", "2bhk balcony", "female only pg", "wifi parking",
           "vegetarian kitchen", "gated sunny", "near IT park"]
SORTS = [None, None, "newest", "price_asc", "price_desc"]

_member_cursor = 0


def _next_member() -> dict | None:
    global _member_cursor
    if not MEMBERS:
        return None
    member = MEMBERS[_member_cursor % len(MEMBERS)]
    _member_cursor += 1
    return member


class Browsing:
    """Listing pages shared by visitors and members."""

    listing_ids: list = []

    def browse_city(self) -> None:
        params = {"city": random.choice(CITIES), "limit": 20}
        sort = random.choice(SORTS)
        if sort:
            params["sort"] = sort
        if random.random() < 0.3:
            params["max_rent"] = random.choice([10000, 15000, 25000, 40000])
        if random.random() < 0.2:
            params["property_category"] = random.choice(["pg", "apartment", "co_living"])
        with self.client.get(f"{API}/properties/", params=params, name=f"{API}/properties/ [city]",
                             catch_response=True) as res:
            if res.status_code == 200:
                ids = [p["id"] for p in res.json()]
                if ids:
                    self.listing_ids = (self.listing_ids + ids)[-200:]
                res.success()
            else:
                res.failure(f"HTTP {res.status_code}")

    def search_text(self) -> None:
        params = {"q": random.choice(QUERIES), "city": random.choice(CITIES), "limit": 20}
        self.client.get(f"{API}/properties/", params=params, name=f"{API}/properties/ [text]")

    def open_listing(self) -> None:
        if not self.listing_ids:
            self.browse_city()
            return
        listing = random.choice(self.listing_ids)
        self.client.get(f"{API}/properties/{listing}", name=f"{API}/properties/{{id}}")


class Visitor(Browsing, HttpUser):
    weight = 6
    wait_time = between(3, 10)

    def on_start(self) -> None:
        self.listing_ids = []
        self.client.get(f"{API}/meta/app-config", name=f"{API}/meta/app-config")
        self.client.get(f"{API}/locations/cities", name=f"{API}/locations/cities")

    @task(4)
    def browse_page(self) -> None:
        # What the /properties page's server render asks for: the anonymous recommended order.
        params = {"sort": "recommended", "limit": 20}
        if random.random() < 0.5:
            params["city"] = random.choice(CITIES)
        self.client.get(f"{API}/properties/", params=params, name=f"{API}/properties/ [browse]")

    @task(6)
    def city_page(self) -> None:
        self.browse_city()

    @task(5)
    def listing_page(self) -> None:
        self.open_listing()

    @task(2)
    def text_search(self) -> None:
        self.search_text()

    @task(1)
    def search_endpoint(self) -> None:
        self.client.post(f"{API}/search/properties", name=f"{API}/search/properties",
                         json={"city": random.choice(CITIES), "limit": 20})

    @task(1)
    def states(self) -> None:
        self.client.get(f"{API}/locations/states", name=f"{API}/locations/states")


class Member(Browsing, HttpUser):
    weight = 3
    wait_time = between(3, 10)

    def on_start(self) -> None:
        self.listing_ids = []
        member = _next_member()
        if member is None:
            raise RuntimeError("no members: run loadtests/seed_load.py first")
        self.client.headers["Authorization"] = f"Bearer {member['token']}"
        self.client.get(f"{API}/auth/me", name=f"{API}/auth/me")

    @task(4)
    def unread(self) -> None:
        self.client.get(f"{API}/notifications/unread-count", name=f"{API}/notifications/unread-count")

    @task(3)
    def city_page(self) -> None:
        self.browse_city()

    @task(3)
    def listing_page(self) -> None:
        self.open_listing()

    @task(2)
    def recommended(self) -> None:
        self.client.get(f"{API}/properties/", name=f"{API}/properties/ [recommended]",
                        params={"sort": "recommended", "city": random.choice(CITIES), "limit": 20})

    @task(2)
    def conversations(self) -> None:
        self.client.get(f"{API}/messaging/conversations", name=f"{API}/messaging/conversations")

    @task(1)
    def notifications(self) -> None:
        self.client.get(f"{API}/notifications/", name=f"{API}/notifications/")

    @task(1)
    def matches(self) -> None:
        # Flatmate matches need a profile; new members get 404 until they make one.
        with self.client.get(f"{API}/matching/recommendations", name=f"{API}/matching/recommendations",
                             catch_response=True) as res:
            if res.status_code in (200, 404):
                res.success()
            else:
                res.failure(f"HTTP {res.status_code}")

    @task(1)
    def profile(self) -> None:
        # New members have no profile yet: 404 is the right answer, not a failure.
        with self.client.get(f"{API}/profiles/me", name=f"{API}/profiles/me", catch_response=True) as res:
            if res.status_code in (200, 404):
                res.success()
            else:
                res.failure(f"HTTP {res.status_code}")


class SignIn(HttpUser):
    """Real sign-ins, paced under the per-IP limit (60 per 5 minutes) from one load generator."""

    fixed_count = 1
    wait_time = constant_pacing(6)

    @task
    def sign_in(self) -> None:
        member = random.choice(MEMBERS) if MEMBERS else None
        if member is None:
            return
        self.client.post(f"{API}/auth/login", name=f"{API}/auth/login",
                         json={"email": member["email"], "password": DATA["password"]})


@events.quitting.add_listener
def _verdict(environment, **_kwargs) -> None:
    stats = environment.stats.total
    if not stats.num_requests:
        return
    max_fail = float(os.environ.get("MAX_FAIL_RATIO", "0.01"))
    max_p95 = float(os.environ.get("MAX_P95_MS", "800"))
    p95 = stats.get_response_time_percentile(0.95)
    problems = []
    if stats.fail_ratio > max_fail:
        problems.append(f"failures {stats.fail_ratio:.2%} > {max_fail:.2%}")
    if p95 > max_p95:
        problems.append(f"p95 {p95:.0f} ms > {max_p95:.0f} ms")
    summary = (f"{stats.num_requests} requests, {stats.total_rps:.0f}/s, failures {stats.fail_ratio:.2%},"
               f" p50 {stats.median_response_time:.0f} ms, p95 {p95:.0f} ms")
    if problems:
        print(f"LOAD TEST FAILED: {'; '.join(problems)} ({summary})")
        environment.process_exit_code = 1
    else:
        print(f"LOAD TEST PASSED: {summary}")
        environment.process_exit_code = 0
