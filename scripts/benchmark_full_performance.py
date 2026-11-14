"""
Comprehensive Performance and Resilience Benchmark Drill
Measures end-to-end HTTP API latency percentiles (p50, p95, p99),
concurrent load handling, and database query throughput.
"""
import time
import asyncio
import statistics
import httpx
import sys

BASE_URL = "http://127.0.0.1:8001"

async def measure_endpoint(client: httpx.AsyncClient, name: str, method: str, path: str, json_body=None, headers=None, n=50):
    latencies = []
    errors = 0
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            if method == "GET":
                r = await client.get(path, headers=headers)
            else:
                r = await client.post(path, json=json_body, headers=headers)
            t1 = time.perf_counter()
            if r.status_code in (200, 201):
                latencies.append((t1 - t0) * 1000.0)
            else:
                errors += 1
        except Exception:
            errors += 1

    if not latencies:
        print(f"{name:<40}: ALL REQUESTS FAILED (Errors: {errors})")
        return {}

    latencies.sort()
    mean_val = statistics.mean(latencies)
    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    min_val = min(latencies)
    max_val = max(latencies)

    print(f"{name:<35}: n={len(latencies)} | p50={p50:6.2f}ms | p95={p95:6.2f}ms | p99={p99:6.2f}ms | mean={mean_val:6.2f}ms (err={errors})")
    return {
        "n": len(latencies),
        "mean": mean_val,
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "min": min_val,
        "max": max_val,
        "errors": errors,
    }

async def benchmark_concurrency(n_concurrent=50):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        t0 = time.perf_counter()
        tasks = [client.get("/health") for _ in range(n_concurrent)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        t1 = time.perf_counter()
        successes = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
        total_time_ms = (t1 - t0) * 1000.0
        rps = (n_concurrent / (t1 - t0))
        print(f"\n--- Concurrent Throughput ({n_concurrent} parallel requests) ---")
        print(f"Total time: {total_time_ms:.2f}ms | Success: {successes}/{n_concurrent} | Throughput: {rps:.1f} req/sec")

async def run_benchmarks():
    print("==================================================================")
    print("Flatmate Platform End-to-End HTTP Performance Benchmark")
    print("==================================================================")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        # Measure health
        await measure_endpoint(client, "System Liveness (/health)", "GET", "/health", n=100)
        # Measure catalog
        await measure_endpoint(client, "Property Catalog (/properties)", "GET", "/api/v1/properties", n=50)
        # Measure search
        await measure_endpoint(
            client,
            "Geospatial Radius Search",
            "POST",
            "/api/v1/search/properties",
            json_body={"city": "Bengaluru", "latitude": 12.9716, "longitude": 77.5946, "radius_km": 15.0},
            n=50
        )

        # Login to get auth token
        r_login = await client.post("/api/v1/auth/login", json={"email": "seeker_d4cada@staging.example.com", "password": "Password123!"})
        if r_login.status_code == 200:
            token = r_login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            await measure_endpoint(client, "Current User Profile (/auth/me)", "GET", "/api/v1/auth/me", headers=headers, n=50)
            await measure_endpoint(client, "Active Notifications Feed", "GET", "/api/v1/notifications/", headers=headers, n=50)

    # Concurrency test
    await benchmark_concurrency(50)

if __name__ == "__main__":
    asyncio.run(run_benchmarks())
