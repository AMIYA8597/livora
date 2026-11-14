import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

async def setup_buckets():
    url = os.getenv("SUPABASE_URL", "https://qjwitdovbsfviaepjcul.supabase.co")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
    if not service_key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SECRET_KEY environment variable required")
        return
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    
    buckets = [
        {"id": "property-photos", "name": "property-photos", "public": True},
        {"id": "verification-docs", "name": "verification-docs", "public": False},
        {"id": "avatars", "name": "avatars", "public": True},
        {"id": "chat-attachments", "name": "chat-attachments", "public": False},
    ]
    
    async with httpx.AsyncClient() as client:
        for b in buckets:
            r = await client.post(f"{url}/storage/v1/bucket", headers=headers, json=b)
            print(f"Bucket {b['id']} create status:", r.status_code, r.text)

        # List all buckets
        list_resp = await client.get(f"{url}/storage/v1/bucket", headers=headers)
        print("Live buckets in Supabase:", list_resp.status_code, list_resp.json())

if __name__ == "__main__":
    asyncio.run(setup_buckets())
