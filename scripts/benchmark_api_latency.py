import asyncio
import httpx
import time
import numpy as np

BASE_URL = "http://127.0.0.1:8001"

async def benchmark_endpoint(client: httpx.AsyncClient, name: str, url: str, method: str = "GET", headers=None, json=None, n=100):
    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        if method == "GET":
            r = await client.get(url, headers=headers)
        else:
            r = await client.post(url, headers=headers, json=json)
        t1 = time.perf_counter()
        assert r.status_code in (200, 201), f"Unexpected status {r.status_code}: {r.text}"
        latencies.append((t1 - t0) * 1000)

    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    mean = np.mean(latencies)
    print(f"{name:<35}: Mean={mean:.2f}ms | p50={p50:.2f}ms | p95={p95:.2f}ms | p99={p99:.2f}ms (n={n})")
    return {"mean": mean, "p50": p50, "p95": p95, "p99": p99}

async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        print("--- HTTP API Latency Benchmarks (Local Staging) ---")
        await benchmark_endpoint(client, "Health Check (/health)", "/health")
        await benchmark_endpoint(client, "Property Catalog (/api/v1/properties)", "/api/v1/properties")
        await benchmark_endpoint(client, "Geospatial Search (/search/properties)", "/api/v1/search/properties", method="POST", json={"city": "Bengaluru"})

if __name__ == "__main__":
    asyncio.run(main())
