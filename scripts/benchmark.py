"""Performance benchmark runner for Nagarkot Access Control Service.

Measures p50, p90, p95, and p99 query latency for /me/queue and /jobs first-page
queries against a dataset of 200,000 jobs and 500 users.
Target: p95 latency under 200ms.
"""
import argparse
import os
import statistics
import time
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db, init_db
from app.models import Job, User


def run_benchmark(db_url: str = "sqlite:///./scale.db", iterations: int = 100):
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
        echo=False,
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=True)

    db = Session()
    job_count = db.query(Job).count()
    user_count = db.query(User).count()
    db.close()

    print("================================================================================")
    print(" NAGARKOT ACCESS CONTROL SERVICE - PERFORMANCE BENCHMARK")
    print(f" Database:       {db_url}")
    print(f" Database Scale: {job_count:,} Jobs | {user_count:,} Users")
    print(f" Sample Size:    {iterations} iterations per scenario")
    print(" Target SLA:     p95 latency < 200 ms")
    print("================================================================================\n")

    scenarios = [
        ("GET /me/queue (Asha Rao - National Maker)", "/me/queue?limit=50", "asha-rao"),
        ("GET /me/queue (Rohit Mehta - Restricted Checker)", "/me/queue?limit=50", "rohit-mehta"),
        ("GET /me/queue (Pooja Sharma - Checker + Delhi Cover)", "/me/queue?limit=50", "pooja-sharma"),
        ("GET /me/queue (Neha Kulkarni - Filer MUM & NS)", "/me/queue?limit=50", "neha-kulkarni"),
        ("GET /jobs (Asha Rao - Staff View First Page)", "/jobs?limit=50", "asha-rao"),
        ("GET /jobs (Rajesh Gupta - Client User C01 View)", "/jobs?limit=50", "rajesh-gupta"),
    ]

    results = []

    # Warmup run
    print("Executing warmup requests...")
    for _, path, user_id in scenarios:
        client.get(path, headers={"X-User-Id": user_id})

    print("Running benchmarks...\n")

    for label, path, user_id in scenarios:
        latencies = []
        headers = {"X-User-Id": user_id}

        for _ in range(iterations):
            t0 = time.perf_counter()
            resp = client.get(path, headers=headers)
            t1 = time.perf_counter()

            if resp.status_code != 200:
                print(f"Error {resp.status_code}: {resp.text}")
                continue

            latencies.append((t1 - t0) * 1000.0)  # Convert to ms

        latencies.sort()
        n = len(latencies)

        min_lat = min(latencies)
        mean_lat = statistics.mean(latencies)
        p50 = latencies[int(n * 0.50)]
        p90 = latencies[int(n * 0.90)]
        p95 = latencies[int(n * 0.95)]
        p99 = latencies[min(int(n * 0.99), n - 1)]
        max_lat = max(latencies)

        meets_sla = p95 < 200.0
        sla_badge = "PASS" if meets_sla else "FAIL"

        results.append({
            "scenario": label,
            "min": min_lat,
            "mean": mean_lat,
            "p50": p50,
            "p90": p90,
            "p95": p95,
            "p99": p99,
            "max": max_lat,
            "sla": sla_badge,
        })

    # Print Markdown Table
    print("| Scenario | Min (ms) | Mean (ms) | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | SLA (<200ms) |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for r in results:
        print(
            f"| {r['scenario']} | {r['min']:.2f} | {r['mean']:.2f} | {r['p50']:.2f} | "
            f"{r['p90']:.2f} | **{r['p95']:.2f}** | {r['p99']:.2f} | {r['sla']} |"
        )

    print("\nBenchmark completed successfully.")
    app.dependency_overrides.clear()
    engine.dispose()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run performance benchmark")
    parser.add_argument("--db", type=str, default="sqlite:///./scale.db", help="Target DB to benchmark")
    parser.add_argument("--iterations", type=int, default=100, help="Number of iterations per test")
    args = parser.parse_args()

    run_benchmark(db_url=args.db, iterations=args.iterations)
