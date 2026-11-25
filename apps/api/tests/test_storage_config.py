"""Storage backend selection must never silently degrade to fake URLs."""
import pytest

from app.infrastructure import storage as storage_mod
from app.infrastructure.storage import (
    LocalStorageProvider,
    StorageConfigurationError,
    SupabaseStorageProvider,
    init_storage,
)


@pytest.fixture(autouse=True)
def reset_storage_singleton(monkeypatch):
    original = storage_mod._storage_instance
    yield
    storage_mod._storage_instance = original


def _configure(monkeypatch, **values):
    for key, value in values.items():
        monkeypatch.setattr(storage_mod.settings, key, value)


def test_local_storage_allowed_in_test(monkeypatch):
    _configure(monkeypatch, STORAGE_TYPE="local", ENVIRONMENT="test")
    assert isinstance(init_storage(), LocalStorageProvider)


@pytest.mark.parametrize("env", ["staging", "production"])
def test_local_storage_refused_outside_dev(monkeypatch, env):
    _configure(monkeypatch, STORAGE_TYPE="local", ENVIRONMENT=env)
    with pytest.raises(StorageConfigurationError):
        init_storage()


def test_supabase_without_credentials_fails(monkeypatch):
    _configure(monkeypatch, STORAGE_TYPE="supabase", SUPABASE_URL="", SUPABASE_SECRET_KEY="",
               SUPABASE_SERVICE_ROLE_KEY="")
    with pytest.raises(StorageConfigurationError):
        init_storage()


def test_supabase_uses_the_secret_key_before_the_legacy_one(monkeypatch):
    used = {}

    class _Provider:
        def __init__(self, url, key):
            used["key"] = key

        def verify_buckets(self):
            pass

    monkeypatch.setattr(storage_mod, "SupabaseStorageProvider", _Provider)
    _configure(monkeypatch, STORAGE_TYPE="supabase", SUPABASE_URL="https://p.supabase.co",
               SUPABASE_SECRET_KEY="new-secret-key", SUPABASE_SERVICE_ROLE_KEY="legacy-key")
    init_storage()
    assert used["key"] == "new-secret-key"
    _configure(monkeypatch, SUPABASE_SECRET_KEY="")
    init_storage()
    assert used["key"] == "legacy-key"  # still works until the secret key is set


def test_unknown_storage_type_fails(monkeypatch):
    _configure(monkeypatch, STORAGE_TYPE="s3-typo", ENVIRONMENT="production")
    with pytest.raises(StorageConfigurationError):
        init_storage()


def test_supabase_signed_url_missing_raises():
    provider = SupabaseStorageProvider.__new__(SupabaseStorageProvider)

    class _Bucket:
        def create_signed_url(self, path, expires_in):
            return {}

    class _Storage:
        def from_(self, bucket):
            return _Bucket()

    class _Client:
        storage = _Storage()

    provider.client = _Client()
    with pytest.raises(StorageConfigurationError):
        provider.get_signed_url("kyc", "doc.pdf")


def test_transaction_pooler_disables_prepared_statement_cache():
    from app.core.database import engine_options, uses_transaction_pooler

    pooled = "postgresql+asyncpg://u:p@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"
    session = "postgresql+asyncpg://u:p@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
    assert uses_transaction_pooler(pooled)
    assert not uses_transaction_pooler(session)
    args = engine_options(pooled)["connect_args"]
    assert args["statement_cache_size"] == 0
    assert args["prepared_statement_name_func"]() != args["prepared_statement_name_func"]()
    assert "connect_args" not in engine_options(session)


# --- Supabase bucket verification at startup -----------------------------------------------

class _FakeStorage:
    def __init__(self, buckets):
        self._buckets = buckets

    def list_buckets(self):
        return self._buckets


def _provider_with(buckets):
    from app.infrastructure.storage import SupabaseStorageProvider

    provider = SupabaseStorageProvider.__new__(SupabaseStorageProvider)
    provider.client = type("C", (), {"storage": _FakeStorage(buckets)})()
    return provider


def _hosted(**public_overrides):
    base = {"properties": True, "avatars": True, "verification": False, "chat-attachments": False}
    base.update(public_overrides)
    return [{"id": k, "public": v} for k, v in base.items()]


def test_bucket_verification_accepts_correct_hosted_layout():
    _provider_with(_hosted()).verify_buckets()


def test_bucket_verification_refuses_public_private_bucket():
    import pytest
    from app.infrastructure.storage import StorageConfigurationError

    with pytest.raises(StorageConfigurationError, match="must be PRIVATE"):
        _provider_with(_hosted(verification=True)).verify_buckets()


def test_bucket_verification_refuses_missing_bucket():
    import pytest
    from app.infrastructure.storage import StorageConfigurationError

    buckets = [b for b in _hosted() if b["id"] != "chat-attachments"]
    with pytest.raises(StorageConfigurationError, match="does not exist"):
        _provider_with(buckets).verify_buckets()
