"""
Placing new listings on the map with OpenStreetMap's Nominatim.

The listing wizard saves a listing at its city's centre. This job (an outbox event, so it never
slows the owner down and is retried if Nominatim is busy) looks up the listing's PUBLIC locality,
city and PIN code. The flat or building address is never sent anywhere. Public positions are
blurred to about 1 km anyway, so locality-level precision is all "near me" needs.

Nominatim's usage policy (https://operations.osmfoundation.org/policies/nominatim/) is followed:
at most one request per second (shared through Redis across workers, and per process without
it), results cached, an identifying User-Agent, and no bulk or autocomplete use. A match more
than MAX_KM_FROM_CITY from the chosen city is treated as wrong and ignored.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Protocol, Tuple
from uuid import UUID

import httpx
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.locations.service import LocationService, distance_km
from app.modules.messaging.models import OutboxEvent
from app.modules.properties.models import Property

logger = logging.getLogger("flatmate.geocoding")

GEOCODE_EVENT = "listing.geocode"
# A submitted point this close to the city's centre is the wizard's placeholder, not a real pin.
CITY_PIN_KM = 1.0
MAX_KM_FROM_CITY = 50.0
MIN_INTERVAL_SECONDS = 1.1
CACHE_SECONDS = 30 * 24 * 3600
MISS_CACHE_SECONDS = 24 * 3600

Point = Tuple[float, float]


class GeocoderUnavailable(Exception):
    """Busy or down (429/5xx/network): the outbox retries later with backoff."""


class Geocoder(Protocol):
    async def search(self, params: Dict[str, str]) -> Optional[Point]: ...


def queue_listing_geocode(db: AsyncSession, property_id: UUID) -> None:
    """Add (not commit) the job; it commits with the new listing."""
    db.add(OutboxEvent(event_type=GEOCODE_EVENT, payload={"property_id": str(property_id)}, status="pending"))


def precision_for_new_listing(lat: float, lng: float, centre: Optional[Point]) -> str:
    """"city" when the point is just the city's centre (the job will place it), else "owner"."""
    if centre is None:
        return "owner"
    return "city" if distance_km(lat, lng, centre[0], centre[1]) <= CITY_PIN_KM else "owner"


# ---------------------------------------------------------------- Nominatim client

_last_request = 0.0  # per process; Redis coordinates processes when it is reachable


async def _wait_for_slot(redis: Any) -> None:
    global _last_request
    gap = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_request)
    if gap > 0:
        await asyncio.sleep(gap)
    if redis is not None:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if await redis.set("geocode:nominatim:slot", "1", nx=True, px=int(MIN_INTERVAL_SECONDS * 1000)):
                    break
            except Exception:  # noqa: BLE001 - Redis trouble must not block geocoding
                break
            await asyncio.sleep(0.25)
    _last_request = time.monotonic()


class NominatimGeocoder:
    def __init__(self, base_url: str, user_agent: str, email: Optional[str] = None,
                 timeout: float = 8.0, transport: Optional[httpx.AsyncBaseTransport] = None,
                 redis: Any = None):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.email = email
        self.timeout = timeout
        self.transport = transport
        self.redis = redis

    @staticmethod
    def _cache_key(params: Dict[str, str]) -> str:
        raw = json.dumps(sorted((k, v.strip().lower()) for k, v in params.items()))
        return "geocode:v1:" + hashlib.sha256(raw.encode()).hexdigest()

    async def _cached(self, key: str) -> Optional[Dict[str, Any]]:
        if self.redis is None:
            return None
        try:
            raw = await self.redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:  # noqa: BLE001
            return None

    async def _remember(self, key: str, value: Dict[str, Any], seconds: int) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.set(key, json.dumps(value), ex=seconds)
        except Exception:  # noqa: BLE001
            pass

    async def search(self, params: Dict[str, str]) -> Optional[Point]:
        key = self._cache_key(params)
        cached = await self._cached(key)
        if cached is not None:
            return tuple(cached["point"]) if cached.get("point") else None  # type: ignore[return-value]

        query = {**params, "format": "jsonv2", "limit": "1", "countrycodes": "in"}
        if self.email:
            query["email"] = self.email
        await _wait_for_slot(self.redis)
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport,
                                         headers={"User-Agent": self.user_agent}) as client:
                res = await client.get(f"{self.base_url}/search", params=query)
        except httpx.HTTPError as exc:
            raise GeocoderUnavailable(type(exc).__name__) from exc
        if res.status_code == 429 or res.status_code >= 500:
            raise GeocoderUnavailable(f"HTTP {res.status_code}")
        res.raise_for_status()
        rows = res.json()
        point: Optional[Point] = (float(rows[0]["lat"]), float(rows[0]["lon"])) if rows else None
        await self._remember(key, {"point": list(point) if point else None},
                             CACHE_SECONDS if point else MISS_CACHE_SECONDS)
        return point


# ---------------------------------------------------------------- the job

def _attempts(address_display: str, city: str, state: Optional[str], postal_code: str) -> List[Tuple[str, Dict[str, str]]]:
    """Most to least precise. Only public fields: the locality line, city, state and PIN."""
    locality = address_display.strip()
    if city.lower() not in locality.lower():
        locality = f"{locality}, {city}"
    region = f", {state}" if state else ""
    pin = postal_code.strip()
    tries: List[Tuple[str, Dict[str, str]]] = []
    if pin:
        tries.append(("locality", {"q": f"{locality}{region} {pin}"}))
    tries.append(("locality", {"q": f"{locality}{region}"}))
    if pin:
        tries.append(("postcode", {"postalcode": pin, "country": "India"}))
    return tries


async def _redis_client() -> Any:
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        await client.ping()
        return client
    except Exception:  # noqa: BLE001 - no Redis: per-process throttle, no cache
        return None


async def geocode_listing(session_factory, property_id: UUID, geocoder: Optional[Geocoder] = None) -> Dict[str, Any]:
    """Place a listing that is still at its city's centre. Idempotent: anything not at "city"
    precision is left alone. Returns the outcome for the outbox log (no address in it)."""
    out: Dict[str, Any] = {"property_id": str(property_id)}
    async with session_factory() as db:
        prop = await db.get(Property, property_id)
        if prop is None or prop.location_precision != "city":
            return {**out, "outcome": "skipped"}
        catalogue = await LocationService(db).resolve(prop.city)
        current = to_shape(prop.location)
        centre: Point = (
            (catalogue.latitude, catalogue.longitude)
            if catalogue and catalogue.latitude is not None and catalogue.longitude is not None
            else (current.y, current.x)
        )
        tries = _attempts(prop.address_display, prop.city, prop.state, prop.postal_code)

    redis = None
    if geocoder is None:
        if settings.GEOCODER != "nominatim":
            return {**out, "outcome": "disabled"}
        redis = await _redis_client()
        geocoder = NominatimGeocoder(settings.NOMINATIM_URL, settings.GEOCODER_USER_AGENT,
                                     settings.GEOCODER_EMAIL, settings.GEOCODER_TIMEOUT_SECONDS, redis=redis)
    try:
        for precision, params in tries:
            point = await geocoder.search(params)
            if point is None:
                continue
            if distance_km(point[0], point[1], centre[0], centre[1]) > MAX_KM_FROM_CITY:
                logger.info("Geocode for %s landed outside its city; ignored", property_id)
                continue
            async with session_factory() as db:
                await db.execute(
                    update(Property)
                    .where(Property.id == property_id, Property.location_precision == "city")
                    .values(location=WKTElement(f"POINT({point[1]} {point[0]})", srid=4326),
                            location_precision=precision)
                )
                await db.commit()
            return {**out, "outcome": precision}
        return {**out, "outcome": "not_found"}
    finally:
        if redis is not None:
            try:
                await redis.aclose()
            except Exception:  # noqa: BLE001
                pass
