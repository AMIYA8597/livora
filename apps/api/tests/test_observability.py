"""
Observability: what logs and error reports may contain, request IDs, and the readiness probe.
"""
import json
import logging
import sys

from app import main as main_module
from app.core import observability
from app.core.config import settings
from app.core.logging import JsonFormatter, clean_request_id, cloud_trace, request_id_var, trace_var


def _record(msg, level=logging.INFO, exc_info=None, **extra):
    record = logging.LogRecord("flatmate.test", level, __file__, 1, msg, None, exc_info)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_lines_carry_request_context_and_hide_secrets(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_PROJECT", "flatmate-prod")
    rid = request_id_var.set("req-123")
    trace = trace_var.set(cloud_trace("0123456789abcdef0123456789abcdef/1;o=1"))
    try:
        try:
            raise ValueError('login failed {"password": "hunter2"} with Bearer abc.def.ghi')
        except ValueError:
            line = JsonFormatter().format(_record(
                "GET /api/v1/messaging/ws?token=eyJsecret [500]", logging.ERROR, sys.exc_info(),
                fields={"http": {"status": 500}},
            ))
    finally:
        request_id_var.reset(rid)
        trace_var.reset(trace)
    data = json.loads(line)
    assert data["severity"] == "ERROR" and data["request_id"] == "req-123"
    assert data["logging.googleapis.com/trace"] == "projects/flatmate-prod/traces/0123456789abcdef0123456789abcdef"
    assert data["http"] == {"status": 500}
    assert "eyJsecret" not in data["message"] and "token=[REDACTED]" in data["message"]
    assert "hunter2" not in data["stack_trace"] and "abc.def.ghi" not in data["stack_trace"]
    assert "ValueError" in data["stack_trace"]


def test_aadhaar_numbers_are_hidden_but_ids_are_not():
    from app.core.logging import redact

    for aadhaar in ("1234 5678 9012", "1234-5678-9012", "123456789012"):
        assert redact(f"kyc id {aadhaar} ok") == "kyc id XXXX-XXXX-XXXX ok"
    for kept in ("44568909-4129-47ca-919c-810f6b63435c", "user 75c93110-5321-4a3f-b92a-f71f0464d367",
                 "+91 9876543210", "order_1234567890123"):
        assert redact(kept) == kept


def test_request_ids_and_traces_are_validated(monkeypatch):
    assert clean_request_id("abc-123_DEF.9") == "abc-123_DEF.9"
    for bad in (None, "", "a" * 65, "x\nFAKE LOG LINE", "a b", "<script>"):
        assert clean_request_id(bad) is None
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_PROJECT", None)
    assert cloud_trace("0123456789abcdef0123456789abcdef/1") is None
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_PROJECT", "p")
    assert cloud_trace("not-a-trace/1") is None


def test_error_reports_carry_nothing_personal():
    event = {
        "request": {
            "url": "https://api.flatmate.in/api/v1/x?token=abc",
            "query_string": "token=abc",
            "cookies": {"session": "s"},
            "data": {"password": "hunter2"},
            "headers": {"Authorization": "Bearer abc", "Cookie": "a=b", "User-Agent": "UA", "X-Forwarded-For": "1.2.3.4"},
        },
        "user": {"id": "u1", "email": "a@b.com", "ip_address": "1.2.3.4"},
        "message": 'oops Bearer abc.def',
        "logentry": {"message": "%s failed", "params": ["a@b.com"], "formatted": 'x {"token": "t0k"}'},
        "exception": {"values": [{"value": "Bearer zzz.yyy", "stacktrace": {"frames": [{"vars": {"password": "p"}}]}}]},
        "breadcrumbs": {"values": [{"message": 'sent {"otp": "123456"}', "data": {"url": "https://x/y?code=9"}}]},
    }
    out = observability.scrub_event(event)
    req = out["request"]
    assert req["url"] == "https://api.flatmate.in/api/v1/x"
    assert not {"query_string", "cookies", "data"} & set(req)
    assert req["headers"] == {"User-Agent": "UA"}
    assert out["user"] == {"id": "u1"}
    assert "abc.def" not in out["message"]
    assert "params" not in out["logentry"] and "t0k" not in out["logentry"]["formatted"]
    exc = out["exception"]["values"][0]
    assert "zzz" not in exc["value"] and "vars" not in exc["stacktrace"]["frames"][0]
    crumb = out["breadcrumbs"]["values"][0]
    assert "123456" not in crumb["message"] and crumb["data"]["url"] == "https://x/y"


def test_sentry_starts_only_with_a_dsn_and_without_pii(monkeypatch):
    calls = []
    import sentry_sdk

    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: calls.append(kw))
    monkeypatch.setattr(sentry_sdk, "set_tag", lambda *a: None)
    monkeypatch.setattr(observability, "_enabled", False)
    monkeypatch.setattr(settings, "SENTRY_DSN", None)
    assert observability.init_sentry("api") is False and calls == []

    monkeypatch.setattr(settings, "SENTRY_DSN", "https://public@o0.ingest.sentry.io/0")
    monkeypatch.setattr(settings, "APP_RELEASE", "abc123")
    assert observability.init_sentry("api") is True
    [kw] = calls
    assert kw["send_default_pii"] is False and kw["include_local_variables"] is False
    assert kw["max_request_body_size"] == "never" and kw["before_send"] is observability.scrub_event
    assert kw["release"] == "abc123"


async def test_responses_carry_a_safe_request_id(async_client):
    res = await async_client.get("/health", headers={"X-Request-ID": "trace-42"})
    assert res.headers["X-Request-ID"] == "trace-42"
    res = await async_client.get("/health", headers={"X-Request-ID": "bad id\r\nINJECTED"})
    assert res.headers["X-Request-ID"] != "bad id\r\nINJECTED" and len(res.headers["X-Request-ID"]) == 36


async def test_readiness_checks_the_database(async_client, monkeypatch):
    res = await async_client.get("/health/ready")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ready" and body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["redis"]["status"] in ("ok", "unavailable", "error")
    assert res.headers["Cache-Control"] == "no-store"

    async def down():
        raise ConnectionError("db is down")

    monkeypatch.setattr(main_module, "_check_database", down)
    res = await async_client.get("/ready")
    assert res.status_code == 503
    assert res.json()["status"] == "not_ready" and res.json()["checks"]["database"] == {"status": "error"}
    assert "db is down" not in res.text
