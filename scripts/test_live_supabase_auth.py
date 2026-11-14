import httpx
import uuid

def test_auth():
    url = "https://qjwitdovbsfviaepjcul.supabase.co"
    anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFqd2l0ZG92YnNmdmlhZXBqY3VsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTQ2MzM0MzEsImV4cCI6MjExMDIwOTQzMX0.YKgDfTU8ONUeJXvhTumLnJm1nalw22FAwE1NfZMTdM0"
    service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFqd2l0ZG92YnNmdmlhZXBqY3VsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5NDYzMzQzMSwiZXhwIjoyMTEwMjA5NDMxfQ.cws1o2WJ4eVfNIaLO780t32TBOx5XtbgCruf99X_sVo"
    
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
