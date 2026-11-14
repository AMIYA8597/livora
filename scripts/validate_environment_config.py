"""
Zero-Leak Environment and Credential Configuration Validator.
Validates the presence, format, and structure of configuration variables
without logging or displaying secret values.
"""
import os
import sys
import re
from urllib.parse import urlparse
from typing import Dict, Any, List, Tuple

def validate_url(url: str, schemes: Tuple[str, ...] = ("http", "https")) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in schemes and bool(p.netloc)
    except Exception:
        return False

def is_jwt_format(val: str) -> bool:
    parts = val.strip().split(".")
    return len(parts) == 3 and all(len(p) > 0 for p in parts)

def validate_config(env_dict: Dict[str, str]) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "frontend": {},
        "backend": {},
        "storage": {},
        "aiml": {},
        "overall_status": "READY",
        "missing_critical": [],
    }

    # Frontend checks
    fe_vars = {
        "NEXT_PUBLIC_APP_URL": ("url", ("http", "https")),
        "NEXT_PUBLIC_API_URL": ("url", ("http", "https")),
        "NEXT_PUBLIC_SUPABASE_URL": ("url", ("http", "https")),
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": ("jwt", None),
        "NEXT_PUBLIC_WS_URL": ("url", ("ws", "wss")),
    }

    for var, (vtype, extra) in fe_vars.items():
        val = env_dict.get(var, "")
        if not val:
            report["frontend"][var] = {"present": False, "valid": False, "note": "Missing"}
        elif vtype == "url":
            valid = validate_url(val, extra)
            report["frontend"][var] = {"present": True, "valid": valid, "scheme": urlparse(val).scheme}
        elif vtype == "jwt":
            valid = is_jwt_format(val)
            report["frontend"][var] = {"present": True, "valid": valid, "format": "jwt" if valid else "invalid"}

    # Backend checks
    be_vars = {
        "ENVIRONMENT": ("enum", ("development", "staging", "production")),
        "SECRET_KEY": ("min_len", 32),
        "DATABASE_URL": ("prefix", ("postgresql://", "postgresql+asyncpg://")),
        "SUPABASE_URL": ("url", ("http", "https")),
        "SUPABASE_ANON_KEY": ("jwt", None),
        "SUPABASE_SERVICE_ROLE_KEY": ("jwt", None),
        "SUPABASE_JWT_SECRET": ("min_len", 16),
        "STORAGE_TYPE": ("enum", ("local", "supabase", "s3")),
    }

    for var, (vtype, extra) in be_vars.items():
        val = env_dict.get(var, "")
        if not val:
            report["backend"][var] = {"present": False, "valid": False, "note": "Missing"}
            report["missing_critical"].append(var)
        elif vtype == "min_len":
            valid = len(val) >= extra
            report["backend"][var] = {"present": True, "valid": valid, "length": len(val)}
        elif vtype == "url":
            valid = validate_url(val)
            report["backend"][var] = {"present": True, "valid": valid, "host": urlparse(val).netloc}
        elif vtype == "jwt":
            valid = is_jwt_format(val)
            report["backend"][var] = {"present": True, "valid": valid, "format": "jwt" if valid else "invalid"}
        elif vtype == "enum":
            valid = val in extra
            report["backend"][var] = {"present": True, "valid": valid, "value": val}
        elif vtype == "prefix":
            valid = any(val.startswith(p) for p in extra)
            report["backend"][var] = {"present": True, "valid": valid, "scheme": val.split("://")[0] if "://" in val else "unknown"}

    if report["missing_critical"]:
        report["overall_status"] = "CREDENTIALS_REQUIRED"

    return report

def load_env_file(filepath: str) -> Dict[str, str]:
    data = {}
    if not os.path.exists(filepath):
        return data
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                data[k] = v
    return data

if __name__ == "__main__":
    target_file = sys.argv[1] if len(sys.argv) > 1 else ".env"
    print(f"Validating configuration for: {target_file}")
    env_data = load_env_file(target_file) if os.path.exists(target_file) else dict(os.environ)
    res = validate_config(env_data)
    print(f"Overall Status: {res['overall_status']}")
    print("\n--- Frontend Configuration ---")
    for k, v in res["frontend"].items():
        print(f"  {k:<35}: Present={v.get('present')} Valid={v.get('valid')}")
    print("\n--- Backend Configuration ---")
    for k, v in res["backend"].items():
        print(f"  {k:<35}: Present={v.get('present')} Valid={v.get('valid')}")
    if res["missing_critical"]:
        print(f"\nMissing Critical Variables: {', '.join(res['missing_critical'])}")
