"""
The API contract the mobile apps build on: the committed OpenAPI snapshot matches the code,
the breaking-change check catches what would break an installed app (and nothing else), and
app versions below the supported minimum are told to update.
"""
import copy
import json

import pytest

from app.core import api_contract, client_version
from app.core.config import settings

API = settings.API_V1_PREFIX


def test_committed_snapshot_matches_the_code():
    assert api_contract.main(["check"]) == 0, "run `python -m app.core.api_contract export` in apps/api"


def test_the_snapshot_is_compatible_with_itself_and_covers_the_mobile_endpoints():
    spec = json.loads(api_contract.SNAPSHOT.read_text(encoding="utf-8"))
    assert api_contract.breaking_changes(spec, spec) == []
    for path in (f"{API}/meta/app-config", f"{API}/notifications/push/devices", f"{API}/auth/refresh"):
        assert path in spec["paths"]


def _spec():
    """A small spec in FastAPI's shape: one GET with a response model, one POST with a body."""
    return {
        "openapi": "3.1.0",
        "paths": {
            "/api/v1/items/{item_id}": {"get": {
                "parameters": [{"in": "path", "name": "item_id", "required": True, "schema": {"type": "string"}},
                               {"in": "query", "name": "lang", "required": False, "schema": {"type": "string"}}],
                "responses": {"200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Item"}}}}},
            }},
            "/api/v1/items": {"post": {
                "requestBody": {"required": True, "content": {"application/json": {
                    "schema": {"$ref": "#/components/schemas/ItemCreate"}}}},
                "responses": {"201": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Item"}}}}},
            }},
        },
        "components": {"schemas": {
            "Item": {"type": "object", "required": ["id", "title", "status"], "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "status": {"type": "string", "enum": ["draft", "live"]},
                "rent": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                "tags": {"type": "array", "items": {"$ref": "#/components/schemas/Tag"}},
            }},
            "Tag": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
            "ItemCreate": {"type": "object", "required": ["title"], "properties": {
                "title": {"type": "string", "maxLength": 100},
                "kind": {"type": "string", "enum": ["room", "flat"]},
            }},
        }},
    }


def _changed(edit):
    new = copy.deepcopy(_spec())
    edit(new)
    return api_contract.breaking_changes(_spec(), new)


def _schemas(spec):
    return spec["components"]["schemas"]


def test_additive_changes_are_not_breaking():
    def additive(s):
        _schemas(s)["Item"]["properties"]["photos"] = {"type": "integer"}  # new response field
        _schemas(s)["ItemCreate"]["properties"]["notes"] = {"type": "string"}  # new optional request field
        _schemas(s)["ItemCreate"]["properties"]["kind"]["enum"].append("pg")  # accepts more
        _schemas(s)["ItemCreate"]["properties"]["title"]["maxLength"] = 200  # accepts longer
        _schemas(s)["Item"]["properties"]["rent"] = {"type": "integer"}  # never null any more
        s["paths"]["/api/v1/other"] = {"get": {"responses": {"200": {}}}}  # new endpoint
        # A component renamed with the same shape.
        _schemas(s)["Label"] = _schemas(s).pop("Tag")
        _schemas(s)["Item"]["properties"]["tags"]["items"] = {"$ref": "#/components/schemas/Label"}
    assert _changed(additive) == []


@pytest.mark.parametrize("edit, expected", [
    (lambda s: s["paths"].pop("/api/v1/items"), "POST /api/v1/items: operation removed"),
    (lambda s: _schemas(s)["Item"]["properties"].pop("title"),
     "GET /api/v1/items/{item_id} 200 response.title: response field removed"),
    (lambda s: _schemas(s)["Item"]["required"].remove("status"),
     "GET /api/v1/items/{item_id} 200 response.status: response field no longer always present"),
    (lambda s: _schemas(s)["Item"]["properties"].__setitem__("title", {"anyOf": [{"type": "string"}, {"type": "null"}]}),
     "GET /api/v1/items/{item_id} 200 response.title: response type changed from ['string'] to ['null', 'string']"),
    (lambda s: _schemas(s)["Item"]["properties"]["status"]["enum"].append("archived"),
     "GET /api/v1/items/{item_id} 200 response.status: new response values ['\"archived\"']"),
    (lambda s: _schemas(s)["Tag"]["properties"].pop("name"),
     "GET /api/v1/items/{item_id} 200 response.tags[].name: response field removed"),
    (lambda s: _schemas(s)["ItemCreate"]["required"].append("kind"),
     "POST /api/v1/items request.kind: new required request field"),
    (lambda s: _schemas(s)["ItemCreate"]["properties"]["kind"]["enum"].remove("flat"),
     "POST /api/v1/items request.kind: no longer accepts values ['\"flat\"']"),
    (lambda s: _schemas(s)["ItemCreate"]["properties"]["title"].__setitem__("maxLength", 50),
     "POST /api/v1/items request.title: maxLength tightened from 100 to 50"),
    (lambda s: s["paths"]["/api/v1/items/{item_id}"]["get"]["parameters"][1].__setitem__("required", True),
     "GET /api/v1/items/{item_id}: new required query parameter 'lang'"),
    (lambda s: s["paths"]["/api/v1/items"]["post"].__setitem__("responses", {"200": s["paths"]["/api/v1/items"]["post"]["responses"]["201"]}),
     "POST /api/v1/items: success status changed from ['201'] to ['200']"),
])
def test_breaking_changes_are_reported(edit, expected):
    assert expected in _changed(edit)


def test_accepted_breaking_changes_are_listed_on_purpose(tmp_path):
    problems = _changed(lambda s: s["paths"].pop("/api/v1/items"))
    accepted = tmp_path / "accepted.txt"
    accepted.write_text("# removed before any app shipped\nPOST /api/v1/items: operation removed\n", encoding="utf-8")
    assert api_contract.unaccepted(problems, api_contract.accepted_changes(accepted)) == []
    assert api_contract.accepted_changes(tmp_path / "missing.txt") == set()


# ---------------------------------------------------------------------------- app versions

def test_version_parsing_and_policy(monkeypatch):
    assert client_version.parse_version("1.4") == (1, 4, 0, 0)
    assert client_version.parse_version("1.10.0") > client_version.parse_version("1.9.9")
    for bad in ("", None, "v1.2", "1..2", "1.2.3.4.5", "1.2-beta"):
        assert client_version.parse_version(bad) is None

    monkeypatch.setattr(settings, "MIN_APP_VERSION_ANDROID", "1.4.0")
    monkeypatch.setattr(settings, "MIN_APP_VERSION_IOS", None)
    assert client_version.upgrade_required("android", "1.3.9")["min_version"] == "1.4.0"
    assert client_version.upgrade_required("Android", None) is not None  # an app that won't say is too old
    assert client_version.upgrade_required("android", "1.4") is None
    assert client_version.upgrade_required("android", "2.0.1") is None
    assert client_version.upgrade_required("ios", "0.1") is None  # no iOS minimum
    assert client_version.upgrade_required(None, "0.1") is None  # the website
    assert client_version.upgrade_required("web", "0.1") is None


async def test_outdated_apps_are_told_to_update(async_client, monkeypatch):
    monkeypatch.setattr(settings, "MIN_APP_VERSION_IOS", "2.0")
    monkeypatch.setattr(settings, "LATEST_APP_VERSION_IOS", "2.1.0")
    monkeypatch.setattr(settings, "APP_STORE_URL_IOS", "https://apps.apple.com/app/id000")
    old = {"X-Client-Platform": "ios", "X-Client-Version": "1.9.3"}

    res = await async_client.get(f"{API}/properties", headers=old)
    assert res.status_code == 426 and res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert body["error_code"] == "CLIENT_UPGRADE_REQUIRED" and body["min_version"] == "2.0"
    assert body["update_url"] == "https://apps.apple.com/app/id000" and body["request_id"]

    # The update screen's data and health checks still answer.
    config = await async_client.get(f"{API}/meta/app-config", headers=old)
    assert config.status_code == 200
    assert config.json()["ios"] == {"min_version": "2.0", "latest_version": "2.1.0",
                                    "update_url": "https://apps.apple.com/app/id000"}
    assert config.json()["api_version"] == "v1" and "max-age" in config.headers["cache-control"]
    assert (await async_client.get("/health/live", headers=old)).status_code == 200

    # Current apps, Android (no minimum) and the website are unaffected.
    for headers in ({"X-Client-Platform": "ios", "X-Client-Version": "2.0.0"},
                    {"X-Client-Platform": "android", "X-Client-Version": "0.1"}, {}):
        assert (await async_client.get(f"{API}/meta/app-config", headers=headers)).status_code == 200
        assert (await async_client.get(f"{API}/locations/cities", headers=headers)).status_code != 426
