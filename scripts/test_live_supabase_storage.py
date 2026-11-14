import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def test_storage():
    url = os.getenv("SUPABASE_URL", "https://qjwitdovbsfviaepjcul.supabase.co")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY", "")
    if not service_key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY required in environment")
        return
    
    client = create_client(url, service_key)
    
    # 1. Upload a test text file to property-photos
    test_content = b"Flatmate Platform Staging Verification Image Placeholder"
    path = "test/integration_check.txt"
    
    try:
        res = client.storage.from_("property-photos").upload(path, test_content, {"content-type": "text/plain", "upsert": "true"})
        print("Upload success:", res)
    except Exception as e:
        print("Upload result/error:", e)
        
    # 2. Get public url
    public_url = client.storage.from_("property-photos").get_public_url(path)
    print("Public URL:", public_url)
    
    # 3. Get signed url from private bucket
    try:
        client.storage.from_("verification-docs").upload("test/private_doc.txt", b"Private ID Proof", {"content-type": "text/plain", "upsert": "true"})
        signed_url_res = client.storage.from_("verification-docs").create_signed_url("test/private_doc.txt", 3600)
        print("Signed URL response:", signed_url_res)
    except Exception as e:
        print("Signed URL error:", e)

if __name__ == "__main__":
    test_storage()
