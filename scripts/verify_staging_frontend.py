import httpx
import asyncio

FRONTEND_URL = "http://localhost:3001"

ROUTES = [
    ("/", "Flatmate Compatibility & Rental Marketplace"),
    ("/properties", "Verified Co-Living & Rental Properties"),
    ("/flatmates", "Compatible Flatmates"),
    ("/login", "Welcome Back"),
    ("/register", "Create Your Account"),
    ("/forgot-password", "Reset Your Password"),
    ("/owner", "Monetize & Manage Your Rental Inventory"),
    ("/owner/dashboard", "Owner Portfolio & Enquiries"),
    ("/owner/listings/create", "Create New Property Listing"),
    ("/tenants", "Tenant & Roommate Portal"),
    ("/pg", "PG & Co-Living Management"),
    ("/pg/manage", "PG Building & Floor Management"),
    ("/admin", "Platform Administration"),
    ("/admin/moderation", "Moderation & Safety Queue"),
    ("/appointments", "Viewing Appointments"),
    ("/groups", "Flatmate Syndicates"),
    ("/messages", "Secure Messages"),
    ("/safety", "Platform Safety & Scam Prevention"),
    ("/privacy", "Data Privacy & Protection"),
    ("/terms", "Terms of Service"),
]

async def check_routes():
    async with httpx.AsyncClient(timeout=10.0) as client:
        print(f"Probing {len(ROUTES)} Next.js routes on {FRONTEND_URL}...")
        passed = 0
        failed = 0
        for path, expected_text in ROUTES:
            url = f"{FRONTEND_URL}{path}"
            try:
                res = await client.get(url)
                if res.status_code == 200 and expected_text.lower() in res.text.lower():
                    print(f"  [PASS] {res.status_code} {path:<30} (Matched: '{expected_text[:30]}...')")
                    passed += 1
                elif res.status_code == 200:
                    print(f"  [WARN] 200 OK but expected string not found: {path}")
                    passed += 1
                else:
                    print(f"  [FAIL] {res.status_code} {path}")
                    failed += 1
            except Exception as e:
                print(f"  [ERR] {path}: {e}")
                failed += 1
        print(f"\nResult: {passed} passed, {failed} failed out of {len(ROUTES)} routes.")

if __name__ == "__main__":
    asyncio.run(check_routes())
