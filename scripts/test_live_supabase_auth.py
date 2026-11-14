import os
import httpx
import uuid
from dotenv import load_dotenv

load_dotenv()

def test_auth():
    url = os.getenv("SUPABASE_URL", "https://qjwitdovbsfviaepjcul.supabase.co")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY", "")
    if not anon_key or not service_key:
        print("ERROR: SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY required in environment")
        return
    
    headers = {"apikey": anon_key, "Content-Type": "application/json"}
    admin_headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}", "Content-Type": "application/json"}
    
    # 1. Check settings
    with httpx.Client(timeout=10) as client:
        r_settings = client.get(f"{url}/auth/v1/settings", headers=headers)
        print("Auth Settings HTTP status:", r_settings.status_code)
        
        # 2. Test admin user creation (or signup)
        test_email = f"test_seeker_{uuid.uuid4().hex[:6]}@flatmatetest.internal"
        test_pw = "P@ssw0rdSecure!2026"
        
        create_payload = {
            "email": test_email,
            "password": test_pw,
            "email_confirm": True,
            "user_metadata": {"full_name": "Staging Live Verifier", "role": "seeker"}
        }
        r_create = client.post(f"{url}/auth/v1/admin/users", headers=admin_headers, json=create_payload)
        print("Admin user creation status:", r_create.status_code)
        if r_create.status_code in (200, 201):
            user_data = r_create.json()
            user_id = user_data.get("id")
            print("Created Auth User ID:", user_id)
            
            # 3. Test user login via password
            login_payload = {
                "email": test_email,
                "password": test_pw
            }
            r_login = client.post(f"{url}/auth/v1/token?grant_type=password", headers=headers, json=login_payload)
            print("User Login status:", r_login.status_code)
            if r_login.status_code == 200:
                login_data = r_login.json()
                access_token = login_data.get("access_token")
                refresh_token = login_data.get("refresh_token")
                print("Access token received! Length:", len(access_token))
                print("Token type:", login_data.get("token_type"))
                print("Expires in:", login_data.get("expires_in"))
                
                # 4. Test authenticated user verification via access token
                user_headers = {"apikey": anon_key, "Authorization": f"Bearer {access_token}"}
                r_user = client.get(f"{url}/auth/v1/user", headers=user_headers)
                print("Auth get user status:", r_user.status_code, "Verified ID:", r_user.json().get("id") == user_id)
                
                # 5. Clean up test user
                r_del = client.delete(f"{url}/auth/v1/admin/users/{user_id}", headers=admin_headers)
                print("User cleanup status:", r_del.status_code)

if __name__ == "__main__":
    test_auth()
