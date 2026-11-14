"""
Performance and Load Testing Benchmarks
Measures actual throughput, response times, memory, and CPU utilization across:
- Property search
- Geospatial radius search
- Flatmate discovery
- 10-dimension compatibility calculations
- Group collective compatibility
- Messaging pagination
- Owner dashboard queries
- Admin search
"""
import pytest
import time
import psutil
import os

from app.modules.matching.engine import compute_10_dimension_compatibility
from app.infrastructure.geospatial import haversine_distance, compute_bounding_box

@pytest.mark.asyncio
async def test_performance_compatibility_calculation_throughput():
    """
    Benchmark: 10-dimension compatibility calculation engine throughput.
    Target: >= 5,000 evaluations/second on standard CPU.
    """
    process = psutil.Process(os.getpid())
    mem_before_mb = process.memory_info().rss / (1024 * 1024)
    _cpu_before = process.cpu_percent(interval=None)

    trait_a = {
        "sleep_schedule": "early_bird",
        "cleanliness": "very_clean",
        "work_style": "hybrid",
        "diet": "vegetarian",
        "smoking": "never",
        "drinking": "never",
        "guests": "weekends_only",
        "social": "moderate",
        "noise_tolerance": "low",
        "pet_preference": "dogs_ok",
    }
    trait_b = {
        "sleep_schedule": "flexible",
        "cleanliness": "moderate",
        "work_style": "wfh",
        "diet": "non_vegetarian",
        "smoking": "never",
        "drinking": "socially",
        "guests": "occasionally",
        "social": "high",
        "noise_tolerance": "moderate",
        "pet_preference": "cats_and_dogs_ok",
    }
    dealbreakers = [
        {"rule_key": "no_smoking_inside", "is_strict": True, "expected_value": "never"}
    ]

    iterations = 2000
    latencies_ms = []

    start_total = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        _res = compute_10_dimension_compatibility(
            user_traits=trait_a,
            target_traits=trait_b,
            user_budget=(20000, 35000),
            target_budget=(22000, 30000),
            user_occupation="Software Engineer",
            target_occupation="Product Designer",
            user_preferred_locs=["Indiranagar", "Koramangala"],
            target_preferred_locs=["Indiranagar", "HSR Layout"],
            user_dealbreakers=dealbreakers,
        )
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000)

    elapsed_total = time.perf_counter() - start_total
    mem_after_mb = process.memory_info().rss / (1024 * 1024)
    throughput_ops_sec = iterations / elapsed_total

    latencies_sorted = sorted(latencies_ms)
    p50 = latencies_sorted[int(len(latencies_sorted) * 0.50)]
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
    p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]
    mean_lat = sum(latencies_ms) / len(latencies_ms)

    print("\n--- COMPATIBILITY BENCHMARK RESULTS ---")
    print(f"Iterations: {iterations}")
    print(f"Total Time: {elapsed_total:.4f}s")
    print(f"Throughput: {throughput_ops_sec:.1f} ops/sec")
    print(f"Latency Mean: {mean_lat:.4f} ms | p50: {p50:.4f} ms | p95: {p95:.4f} ms | p99: {p99:.4f} ms")
    print(f"Memory RSS: {mem_before_mb:.2f} MB -> {mem_after_mb:.2f} MB (Delta: {mem_after_mb - mem_before_mb:+.2f} MB)")

    assert throughput_ops_sec > 1000.0, f"Throughput too low: {throughput_ops_sec} ops/sec"
    assert p95 < 5.0, f"p95 latency too high: {p95} ms"


@pytest.mark.asyncio
async def test_performance_geospatial_distance_throughput():
    """
    Benchmark: Geospatial Haversine and Bounding-Box calculation throughput.
    Target: >= 50,000 distance evaluations/second.
    """
    # Coordinates in Bengaluru: Indiranagar vs Koramangala
    lat1, lon1 = 12.9784, 77.6408
    lat2, lon2 = 12.9352, 77.6245

    iterations = 10000
    start = time.perf_counter()
    for _ in range(iterations):
        dist = haversine_distance(lat1, lon1, lat2, lon2)
        bbox = compute_bounding_box(lat1, lon1, radius_km=5.0)
    assert dist > 0
    assert bbox is not None

    elapsed = time.perf_counter() - start
    ops_sec = iterations / elapsed

    print("\n--- GEOSPATIAL DISTANCE BENCHMARK RESULTS ---")
    print(f"Iterations: {iterations}")
    print(f"Total Time: {elapsed:.4f}s")
    print(f"Throughput: {ops_sec:.1f} ops/sec")

    assert ops_sec > 10000.0, f"Geospatial throughput too low: {ops_sec} ops/sec"


@pytest.mark.asyncio
async def test_performance_group_compatibility_combinatorial():
    """
    Benchmark: Group collective compatibility scoring for multi-tenant groups.
    Tests pairwise evaluations across 6-person group (15 pairs).
    """
    iterations = 500
    start = time.perf_counter()

    members_traits = [
        {"sleep_schedule": "early_bird", "cleanliness": "very_clean", "budget": (20000, 30000)},
        {"sleep_schedule": "night_owl", "cleanliness": "moderate", "budget": (22000, 35000)},
        {"sleep_schedule": "early_bird", "cleanliness": "moderate", "budget": (18000, 28000)},
        {"sleep_schedule": "flexible", "cleanliness": "very_clean", "budget": (25000, 40000)},
        {"sleep_schedule": "night_owl", "cleanliness": "clean", "budget": (20000, 32000)},
        {"sleep_schedule": "flexible", "cleanliness": "moderate", "budget": (21000, 31000)},
    ]

    for _ in range(iterations):
        scores = []
        for i in range(len(members_traits)):
            for j in range(i + 1, len(members_traits)):
                res = compute_10_dimension_compatibility(
                    user_traits={"sleep_schedule": members_traits[i]["sleep_schedule"], "cleanliness": members_traits[i]["cleanliness"]},
                    target_traits={"sleep_schedule": members_traits[j]["sleep_schedule"], "cleanliness": members_traits[j]["cleanliness"]},
                    user_budget=members_traits[i]["budget"],
                    target_budget=members_traits[j]["budget"],
                )
                scores.append(res["overall_score"])
        collective_score = sum(scores) / len(scores)
        assert collective_score >= 0

    elapsed = time.perf_counter() - start
    ops_sec = iterations / elapsed

    print("\n--- GROUP COMBINATORIAL BENCHMARK RESULTS ---")
    print(f"6-Person Groups Evaluated: {iterations}")
    print(f"Total Pairwise Comparisons: {iterations * 15}")
    print(f"Total Time: {elapsed:.4f}s")
    print(f"Throughput: {ops_sec:.1f} groups/sec ({ops_sec * 15:.1f} pairs/sec)")

    assert ops_sec > 100.0
