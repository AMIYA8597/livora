import asyncio
import httpx

async def setup_buckets():
    url = "https://qjwitdovbsfviaepjcul.supabase.co"
    service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFqd2l0ZG92YnNmdmlhZXBqY3VsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5NDYzMzQzMSwiZXhwIjoyMTEwMjA5NDMxfQ.cws1o2WJ4eVfNIaLO780t32TBOx5XtbgCruf99X_sVo"
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
