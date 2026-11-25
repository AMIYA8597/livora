"""
Provision Supabase Storage buckets from the registry (apps/api/app/infrastructure/storage_buckets.py).

Dry run by default: prints what would change. `--apply` creates missing buckets and sets
visibility, per-file size limits and MIME allow-lists, so Supabase itself rejects oversized
or unexpected files even if a request bypasses the API. Buckets not in the registry are
reported, never deleted.

    python scripts/provision_storage.py            # plan
    python scripts/provision_storage.py --apply    # apply

Reads SUPABASE_URL and SUPABASE_SECRET_KEY (or the legacy SUPABASE_SERVICE_ROLE_KEY) from the
environment or apps/api/.env.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent / "apps" / "api"
sys.path.insert(0, str(API_DIR))
os.chdir(API_DIR)  # so the settings pick up apps/api/.env

from app.core.config import settings  # noqa: E402
from app.infrastructure.storage import SupabaseStorageProvider  # noqa: E402
from app.infrastructure.storage_buckets import bucket_registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="apply the changes (default: dry run)")
    args = parser.parse_args()

    provider = SupabaseStorageProvider(settings.SUPABASE_URL, settings.supabase_server_key)
    storage = provider.client.storage
    actual = provider.list_buckets()
    registry = bucket_registry()
    changes = 0

    for spec in registry.values():
        wanted = {
            "public": spec.public,
            "file_size_limit": spec.max_bytes,
            "allowed_mime_types": sorted(spec.mime_types),
        }
        current = actual.get(spec.physical)
        if current is None:
            print(f"CREATE {spec.physical:18} {wanted}")
            changes += 1
            if args.apply:
                storage.create_bucket(spec.physical, options=wanted)
            continue
        diff = {
            k: (current.get(k), v) for k, v in wanted.items()
            if (sorted(current.get(k) or []) if k == "allowed_mime_types" else current.get(k)) != v
        }
        if diff:
            print(f"UPDATE {spec.physical:18} " + ", ".join(f"{k}: {a!r} -> {b!r}" for k, (a, b) in diff.items()))
            changes += 1
            if args.apply:
                storage.update_bucket(spec.physical, options=wanted)
        else:
            print(f"OK     {spec.physical}")

    known = {s.physical for s in registry.values()}
    for extra in sorted(set(actual) - known):
        print(f"UNUSED {extra:18} not used by the app (public={actual[extra]['public']}); review and delete manually")

    if changes and not args.apply:
        print(f"\n{changes} change(s) planned. Re-run with --apply to make them.")
    elif args.apply:
        provider.verify_buckets()
        print("\nApplied. Buckets verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
