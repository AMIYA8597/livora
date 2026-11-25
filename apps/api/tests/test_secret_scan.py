"""
scripts/secret_scan.py: real credentials are caught, placeholders and local dev URLs are not,
and findings never echo the secret. Secret-shaped test values are assembled at runtime so this
file itself stays clean for the scanner.
"""
import base64
import importlib.util
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "secret_scan", Path(__file__).resolve().parents[3] / "scripts" / "secret_scan.py")
secret_scan = importlib.util.module_from_spec(spec)
sys.modules["secret_scan"] = secret_scan  # dataclasses look the module up by name
spec.loader.exec_module(secret_scan)


def _jwt(claims: dict) -> str:
    enc = lambda obj: base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")  # noqa: E731
    return f"{enc({'alg': 'HS256', 'typ': 'JWT'})}.{enc(claims)}.{'s1gnature' * 3}"


RANDOM = "Zq8vR2kLm9Xw4Tn7Bp3Hc6Jd"  # 24 random-looking characters


def test_real_credentials_are_caught():
    cases = {
        "supabase-service-role-jwt": f'key = "{_jwt({"iss": "supabase", "ref": "abc", "role": "service_role"})}"',
        "supabase-secret-key": "SB=" + "sb_" + "secret_" + RANDOM,
        "private-key": "-----BEGIN " + "PRIVATE KEY-----",
        "anthropic-key": "sk-" + "ant-" + RANDOM,
        "razorpay-live-key": "rzp_" + "live_" + RANDOM,
        "aws-access-key": "AKIA" + "Q2W3E4R5T6Y7U8I9",
        "url-with-password": "postgresql://postgres.ref:" + RANDOM + "@aws-1-ap-south-1.pooler.supabase.com:6543/postgres",
        "secret-setting:RAZORPAY_KEY_SECRET": "RAZORPAY_KEY_SECRET=" + RANDOM,
    }
    for rule, line in cases.items():
        assert rule in secret_scan.scan_line(line), rule


def test_placeholders_local_urls_and_public_keys_pass():
    clean = [
        "DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/flatmate_db",
        "REDIS_URL=redis://:" + RANDOM + "@redis:6379/0",
        "export DATABASE_URL=postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres",
        "url = postgresql://postgres.ref:[YOUR-PASSWORD]@aws-1-ap-south-1.pooler.supabase.com:5432/postgres",
        "DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}",
        "SUPABASE_SERVICE_ROLE_KEY=",
        "SECRET_KEY=production_cryptographic_secret_key_minimum_64_characters_random_hex",
        "SECRET_KEY: test_secret_key_minimum_32_characters_1234567890",
        f"NEXT_PUBLIC_SUPABASE_ANON_KEY={_jwt({'iss': 'supabase', 'role': 'anon'})}",  # public by design
        "RAZORPAY_KEY_SECRET=" + RANDOM + "  # secret-scan: allow (revoked test key, kept for the docs)",
    ]
    for line in clean:
        assert secret_scan.scan_line(line) == [], line


def test_findings_never_print_the_value():
    line = "RAZORPAY_KEY_SECRET=" + RANDOM
    [finding] = secret_scan.scan([("config.env", 3, line)])
    assert str(finding) == "config.env:3: secret-setting:RAZORPAY_KEY_SECRET"
    assert RANDOM not in str(finding)
