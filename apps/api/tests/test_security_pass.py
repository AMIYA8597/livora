"""
Security pass (launch item 16): shared rate limits keyed on verified identities, trusted proxy
handling, upload type sniffing / PDF active content / virus scanning, and trimmed group data.
"""
import asyncio
import base64
import io
import os
import struct
import uuid
import zlib
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import Request, Response
from starlette.datastructures import Headers

from app.core import rate_limit
from app.core.config import settings
from app.core.exceptions import AppException, BadRequestException, RateLimitException
from app.core.middleware import MAX_REQUEST_BODY_BYTES, MAX_UPLOAD_BODY_BYTES, body_limit_for
from app.core.security import create_access_token, create_refresh_token
from app.infrastructure import cache, virus_scan
from app.modules.storage.service import (
    StorageService, pdf_active_content, read_upload, sniff_content_type,
)
from tests.image_samples import make_image


def _request(headers: dict | None = None, peer: str = "10.0.0.9") -> Request:
    return Request({
        "type": "http", "method": "POST", "path": "/x",
        "headers": Headers(headers or {}).raw, "client": (peer, 5000),
    })


# --------------------------------------------------------------------------- client identity

def test_client_ip_ignores_forwarded_for_without_trusted_proxies(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    req = _request({"x-forwarded-for": "1.2.3.4"}, peer="10.0.0.9")
    assert rate_limit.client_ip(req) == "10.0.0.9"


def test_client_ip_takes_the_entry_the_trusted_proxy_wrote(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    # The client forged "6.6.6.6"; the load balancer appended the address it actually saw.
    req = _request({"x-forwarded-for": "6.6.6.6, 203.0.113.7"})
    assert rate_limit.client_ip(req) == "203.0.113.7"
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)
    req = _request({"x-forwarded-for": "6.6.6.6, 203.0.113.7, 10.1.1.1"})
    assert rate_limit.client_ip(req) == "203.0.113.7"


def test_limiter_keys_on_the_verified_user_not_the_token(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    user_id = str(uuid.uuid4())
    limiter = rate_limit.RateLimiter(max_requests=1, key_prefix="t")
    first = create_access_token(user_id, ["seeker"])
    second = create_access_token(user_id, ["seeker"], email="x@example.com")
    assert first != second
    keys = {limiter._extract_client_key(_request({"authorization": f"Bearer {t}"})) for t in (first, second)}
    assert keys == {f"t:user:{user_id}"}


def test_forged_or_refresh_tokens_fall_back_to_the_ip(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    limiter = rate_limit.RateLimiter(key_prefix="t")
    refresh = create_refresh_token(str(uuid.uuid4()), ["seeker"])
    for token in ("not-a-jwt", refresh):
        assert limiter._extract_client_key(_request({"authorization": f"Bearer {token}"})) == "t:ip:10.0.0.9"
    ip_only = rate_limit.RateLimiter(key_prefix="t", scope="ip")
    good = create_access_token(str(uuid.uuid4()), ["seeker"])
    assert ip_only._extract_client_key(_request({"authorization": f"Bearer {good}"})) == "t:ip:10.0.0.9"


async def test_limit_breach_raises_429_with_retry_after():
    limiter = rate_limit.RateLimiter(max_requests=1, window_seconds=30, key_prefix="t429", scope="ip")
    await limiter(_request(), Response())
    with pytest.raises(RateLimitException) as exc:
        await limiter(_request(), Response())
    assert exc.value.status_code == 429
    assert exc.value.headers == {"Retry-After": str(exc.value.retry_after)}
    assert 1 <= exc.value.retry_after <= 30


async def test_disabled_limits_never_block(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    for _ in range(5):
        await rate_limit.hit("off", 1, 60)


def test_hashed_keys_hold_no_email():
    key = rate_limit.hashed("  Priya@Example.com ")
    assert key == rate_limit.hashed("priya@example.com")
    assert "priya" not in key and len(key) == 32


async def _redis_client():
    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await asyncio.wait_for(client.ping(), timeout=1)
        return client
    except Exception:  # noqa: BLE001
        await client.aclose()
    try:
        import fakeredis  # optional locally; CI runs a real Redis

        return fakeredis.FakeAsyncRedis(decode_responses=True)
    except Exception:  # noqa: BLE001 - missing, or a fakeredis release that breaks on this redis-py
        return None


async def test_redis_window_is_shared_and_atomic(monkeypatch):
    client = await _redis_client()
    if client is None:
        pytest.skip("No Redis (or fakeredis with Lua) available")
    monkeypatch.setattr(cache, "redis_client", client)
    key = f"shared-{uuid.uuid4().hex}"
    try:
        results = await asyncio.gather(*(rate_limit.check(key, 5, 60) for _ in range(8)))
        allowed = [r for r in results if r[0]]
        assert len(allowed) == 5
        assert sorted(r[1] for r in allowed) == [0, 1, 2, 3, 4]
        blocked = [r for r in results if not r[0]]
        assert all(1 <= r[2] <= 60 for r in blocked)
        # The per-process store saw none of it: counts live in Redis.
        assert (await rate_limit._memory.is_allowed(key, 5, 60))[0]
    finally:
        await client.delete(f"{rate_limit.KEY_NAMESPACE}:{key}")
        await client.aclose()


async def test_falls_back_to_memory_when_redis_errors(monkeypatch):
    class Broken:
        async def eval(self, *args, **kwargs):
            raise ConnectionError("down")

    monkeypatch.setattr(cache, "redis_client", Broken())
    assert (await rate_limit.check("fallback", 1, 60))[0] is True
    assert (await rate_limit.check("fallback", 1, 60))[0] is False


async def test_login_is_limited_per_account(async_client):
    email = f"nobody-{uuid.uuid4().hex[:8]}@example.com"
    codes = []
    for _ in range(11):
        res = await async_client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
        codes.append(res.status_code)
    assert codes[:10] == [401] * 10
    assert codes[10] == 429
    assert int(res.headers["Retry-After"]) > 0
    assert res.json()["error_code"] == "RATE_LIMITED"
    # A different account from the same address is unaffected.
    other = await async_client.post("/api/v1/auth/login", json={"email": "x" + email, "password": "wrong-password"})
    assert other.status_code == 401


def test_upload_routes_get_a_larger_body_cap():
    assert body_limit_for("/api/v1/storage/upload") == MAX_UPLOAD_BODY_BYTES
    assert body_limit_for("/api/v1/messaging/conversations/abc/attachments") == MAX_UPLOAD_BODY_BYTES
    assert body_limit_for("/api/v1/auth/login") == MAX_REQUEST_BODY_BYTES


# --------------------------------------------------------------------------- uploads

def test_type_comes_from_the_bytes_when_the_client_sends_a_generic_one():
    jpeg = make_image("JPEG")
    assert sniff_content_type(jpeg) == "image/jpeg"
    assert sniff_content_type(make_image("WEBP")) == "image/webp"
    assert StorageService.resolve_content_type(jpeg, "application/octet-stream") == "image/jpeg"
    assert StorageService.resolve_content_type(jpeg, None) == "image/jpeg"
    assert StorageService.resolve_content_type(jpeg, "image/jpg") == "image/jpeg"
    # A specific declared type is kept, so a mismatch is still caught as spoofing.
    assert StorageService.resolve_content_type(jpeg, "image/png") == "image/png"
    with pytest.raises(BadRequestException, match="spoofed"):
        StorageService(storage_provider=object()).validate_file(jpeg, "image/png", "a.png", "properties")


@pytest.mark.parametrize("payload", [
    b"%PDF-1.7\n1 0 obj << /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >>",
    b"%PDF-1.7\n1 0 obj << /S /J#61vaScript >>",
    b"%PDF-1.7\n1 0 obj << /Type /Action /S /Launch /F (cmd.exe) >>",
    b"%PDF-1.7\n1 0 obj << /Names << /EmbeddedFiles 2 0 R >> >>",
])
def test_pdfs_with_active_content_are_rejected(payload):
    assert pdf_active_content(payload)
    with pytest.raises(BadRequestException, match="can't be accepted"):
        StorageService(storage_provider=object()).validate_file(payload, "application/pdf", "doc.pdf", "verification")


def test_plain_pdfs_pass():
    plain = b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n2 0 obj << /Type /Pages /Kids [] /Count 0 >>"
    assert pdf_active_content(plain) is None
    StorageService(storage_provider=object()).validate_file(plain, "application/pdf", "doc.pdf", "verification")



# ---- compressed streams (L10): what a raw byte search can't see

def _stream_obj(num: int, data: bytes, filters: str = "/FlateDecode", extra: str = "", length=None) -> bytes:
    length = f"{len(data)}" if length is None else length
    return (f"{num} 0 obj\n<< {extra} /Length {length} /Filter {filters} >>\nstream\n".encode()
            + data + b"\nendstream\nendobj\n")


def _pdf(*objs: bytes) -> bytes:
    return (b"%PDF-1.7\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\n" + b"".join(objs) + b"%%EOF\n")


_JS_OBJECTS = b"10 0 20 0 << /S /JavaScript /JS (app.alert(1)) >> << /Type /Action >>"


@pytest.mark.parametrize("pdf, expected", [
    # Action hidden in a compressed object stream.
    (_pdf(_stream_obj(3, zlib.compress(_JS_OBJECTS), extra="/Type /ObjStm /N 2 /First 10")), "javascript"),
    # Same, with the name #-escaped inside the stream and the filter name abbreviated.
    (_pdf(_stream_obj(3, zlib.compress(b"10 0 << /S /L#61unch /F (cmd) >>"), "/Fl",
                      extra="/Type /ObjStm /N 1 /First 5")), "launch"),
    # A filter chain: ASCII85 over Flate.
    (_pdf(_stream_obj(3, base64.a85encode(zlib.compress(b"<< /EmbeddedFiles 4 0 R >>")) + b"~>",
                      "[/ASCII85Decode /FlateDecode]", extra="/Type /ObjStm /N 1 /First 0")), "embeddedfiles"),
    # Hex-encoded, with the length given by reference.
    (_pdf(_stream_obj(3, zlib.compress(b"<< /RichMedia 5 0 R >>").hex().encode() + b">",
                      "[/AHx /Fl]", length="9 0 R")), "richmedia"),
    # The object stream's own type #-escaped, after a big compressed image that eats the budget.
    (_pdf(_stream_obj(3, zlib.compress(b"\0" * (70 * 1024 * 1024)), extra="/Type /XObject /Subtype /Image"),
          _stream_obj(4, zlib.compress(_JS_OBJECTS), extra="/Type /Obj#53tm /N 2 /First 10")), "javascript"),
], ids=["objstm-js", "escaped-launch", "a85-chain", "hex-indirect-length", "escaped-objstm-after-image"])
def test_active_content_inside_compressed_streams_is_found(pdf, expected):
    assert expected in pdf_active_content(pdf).lower()
    with pytest.raises(BadRequestException, match="can't be accepted"):
        StorageService(storage_provider=object()).validate_file(pdf, "application/pdf", "doc.pdf", "verification")


@pytest.mark.parametrize("pdf", [
    # An object stream in a filter we can't read.
    _pdf(_stream_obj(3, b"\x80\x0b\x60\x50", "/LZWDecode", extra="/Type /ObjStm /N 1 /First 0")),
    # A damaged object stream.
    _pdf(_stream_obj(3, b"not deflate data at all", extra="/Type /ObjStm /N 1 /First 0")),
    # A zip bomb: 80 MB of zeros, compressed to well under 100 KB.
    _pdf(_stream_obj(3, zlib.compress(b"\0" * (80 * 1024 * 1024), 9), extra="/Type /ObjStm /N 1 /First 0")),
    # Encrypted: the streams can't be read at all.
    b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R /Encrypt 5 0 R >>\n%%EOF",
], ids=["lzw-objstm", "damaged-objstm", "zip-bomb", "encrypted"])
def test_pdfs_that_cant_be_checked_are_refused(pdf):
    assert "can't be checked" in pdf_active_content(pdf)


def test_ordinary_compressed_pdfs_pass():
    page = zlib.compress(b"BT /F1 12 Tf 72 712 Td (Rent receipt: stream of payments) Tj ET")
    objstm = zlib.compress(b"10 0 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pdf = _pdf(
        _stream_obj(3, page),
        _stream_obj(4, objstm, extra="/Type /ObjStm /N 1 /First 5"),
        _stream_obj(5, os.urandom(2048), "/DCTDecode", extra="/Type /XObject /Subtype /Image"),
        _stream_obj(6, b"\x01\x02garbage", "/LZWDecode"),  # an unreadable page drawing holds no actions
    )
    assert pdf_active_content(pdf) is None
    StorageService(storage_provider=object()).validate_file(pdf, "application/pdf", "doc.pdf", "verification")


def test_a_pdf_written_by_a_real_library_passes_and_its_javascript_is_found():
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    plain = io.BytesIO()
    writer.write(plain)
    assert pdf_active_content(plain.getvalue()) is None
    writer.add_js("app.alert('hi');")
    writer.compress_identical_objects()
    scripted = io.BytesIO()
    writer.write(scripted)
    assert pdf_active_content(scripted.getvalue())

@pytest.mark.parametrize("header", [b"#!/bin/sh\n", b"\xcf\xfa\xed\xfe", b"\x7fELF"])
def test_executables_are_rejected_whatever_they_claim(header):
    service = StorageService(storage_provider=object())
    with pytest.raises(BadRequestException):
        service.validate_file(header + b"\x00" * 64, "application/octet-stream", "x", "properties")


class _Upload:
    def __init__(self, data: bytes):
        self._data, self.reads = data, 0

    async def read(self, size: int = -1) -> bytes:
        self.reads += 1
        chunk, self._data = self._data[:size], self._data[size:]
        return chunk


async def test_read_upload_stops_at_the_limit():
    assert await read_upload(_Upload(b"a" * 1000), 1000) == b"a" * 1000
    big = _Upload(b"a" * (3 * 256 * 1024))
    with pytest.raises(BadRequestException, match="exceeds maximum permitted limit"):
        await read_upload(big, 300 * 1024)
    assert big.reads == 2  # stopped as soon as it went over, without reading the rest


async def _fake_clamd(reply: bytes):
    received = bytearray()

    async def handle(reader, writer):
        assert await reader.readexactly(10) == b"zINSTREAM\0"
        while True:
            (size,) = struct.unpack("!L", await reader.readexactly(4))
            if size == 0:
                break
            received.extend(await reader.readexactly(size))
        writer.write(reply)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1], received


async def test_clamd_clean_and_infected(monkeypatch):
    for reply, verdict in ((b"stream: OK\0", "clean"), (b"stream: Eicar-Test-Signature FOUND\0", "infected")):
        server, port, received = await _fake_clamd(reply)
        monkeypatch.setattr(settings, "CLAMAV_HOST", "127.0.0.1")
        monkeypatch.setattr(settings, "CLAMAV_PORT", port)
        data = b"x" * (virus_scan.CHUNK * 2 + 10)
        async with server:
            result = await virus_scan.scan_bytes(data)
        assert result.verdict == verdict
        assert bytes(received) == data
        if verdict == "infected":
            assert result.signature == "Eicar-Test-Signature"
            with pytest.raises(BadRequestException, match="virus scanner"):
                server2, port2, _ = await _fake_clamd(reply)
                monkeypatch.setattr(settings, "CLAMAV_PORT", port2)
                async with server2:
                    await StorageService(storage_provider=object()).virus_scan(data)


async def test_scanner_outage_blocks_uploads_only_when_required(monkeypatch):
    monkeypatch.setattr(settings, "CLAMAV_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "CLAMAV_PORT", 1)  # nothing listens here
    monkeypatch.setattr(settings, "CLAMAV_TIMEOUT_SECONDS", 2.0)
    assert (await virus_scan.scan_bytes(b"x")).verdict == "unavailable"
    service = StorageService(storage_provider=object())
    monkeypatch.setattr(settings, "VIRUS_SCAN_REQUIRED", False)
    await service.virus_scan(b"x")
    monkeypatch.setattr(settings, "VIRUS_SCAN_REQUIRED", True)
    with pytest.raises(AppException) as exc:
        await service.virus_scan(b"x")
    assert exc.value.status_code == 503
    monkeypatch.setattr(settings, "CLAMAV_HOST", "")
    with pytest.raises(AppException):
        await service.virus_scan(b"x")  # required but not configured


# --------------------------------------------------------------------------- groups

def _group(member_ids, creator_id):
    now = datetime.now(timezone.utc)
    gid = uuid.uuid4()
    members = [SimpleNamespace(id=uuid.uuid4(), group_id=gid, user_id=m, role="member", joined_at=now) for m in member_ids]
    wishlist = [SimpleNamespace(id=uuid.uuid4(), group_id=gid, property_id=uuid.uuid4(), added_by=member_ids[0],
                                votes={str(member_ids[0]): "up"}, created_at=now)]
    return SimpleNamespace(id=gid, name="Koramangala 3BHK", description=None, target_budget_total=60000,
                           target_city="Bengaluru", target_move_in=None, created_at=now, updated_at=now,
                           creator_id=creator_id, members=members, wishlist_items=wishlist)


def _viewer(role="seeker"):
    return SimpleNamespace(id=uuid.uuid4(), role=role)


def test_public_group_view_shows_counts_not_people():
    from app.modules.groups.router import group_view

    a, b = uuid.uuid4(), uuid.uuid4()
    group = _group([a, b], a)
    for viewer in (None, _viewer()):
        view = group_view(group, viewer)
        assert view.member_count == 2
        assert view.members == [] and view.wishlist_items == []
        assert view.creator_id is None and view.is_member is False
        assert str(a) not in view.model_dump_json() and str(b) not in view.model_dump_json()


def test_members_and_staff_see_the_group_in_full():
    from app.modules.groups.router import group_view

    a, b = uuid.uuid4(), uuid.uuid4()
    group = _group([a, b], a)
    member = SimpleNamespace(id=b, role="seeker")
    view = group_view(group, member)
    assert view.is_member and view.creator_id == a
    assert {m.user_id for m in view.members} == {a, b}
    assert len(view.wishlist_items) == 1
    staff = group_view(group, _viewer("moderator"))
    assert staff.is_member is False and len(staff.members) == 2
