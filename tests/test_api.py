#!/usr/bin/env python3
"""Automated verification and load simulation suite for Flask + MongoDB on Kubernetes.

Usage:
  python tests/test_api.py --url http://localhost:5000
  python tests/test_api.py --url http://localhost:5000 --stress --duration 60 --concurrency 10
"""

import argparse
import concurrent.futures
import json
import sys
import time
import urllib.error
import urllib.request


def make_request(url, method="GET", data=None, headers=None, timeout=5):
    """Utility to perform HTTP requests using standard library."""
    req_headers = headers or {}
    encoded_data = None
    if data is not None:
        if isinstance(data, dict):
            encoded_data = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(data, (str, bytes)):
            encoded_data = data.encode("utf-8") if isinstance(data, str) else data

    req = urllib.request.Request(url, data=encoded_data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            return status_code, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, body
    except Exception as e:
        return None, str(e)


def run_smoke_tests(base_url):
    print("=" * 60)
    print(f"RUNNING SMOKE TESTS AGAINST: {base_url}")
    print("=" * 60)

    # 1. Test Root Endpoint
    print("\n[1] Testing GET / (Welcome endpoint)...")
    status, body = make_request(f"{base_url}/")
    print(f"    Status: {status}")
    print(f"    Response: {body}")
    assert status == 200, f"Expected 200, got {status}"
    assert "Welcome to the Flask app!" in body, "Welcome message missing"
    print("    --> PASS")

    # 2. Test Liveness & Readiness Probes
    print("\n[2] Testing Health Probes...")
    status, body = make_request(f"{base_url}/health/live")
    print(f"    /health/live -> Status: {status}, Body: {body}")
    assert status == 200, f"Liveness failed: {status}"

    status, body = make_request(f"{base_url}/health/ready")
    print(f"    /health/ready -> Status: {status}, Body: {body}")
    assert status == 200, f"Readiness failed: {status}"
    print("    --> PASS")

    # 3. Test POST /data
    print("\n[3] Testing POST /data (Insert document)...")
    test_doc = {
        "sampleKey": "sampleValue",
        "internName": "Aman",
        "timestamp": time.time(),
    }
    status, body = make_request(f"{base_url}/data", method="POST", data=test_doc)
    print(f"    Status: {status}")
    print(f"    Response: {body}")
    assert status == 201, f"Expected 201, got {status}"
    res_json = json.loads(body)
    assert res_json.get("status") == "Data inserted", "Unexpected response body"
    print("    --> PASS")

    # 4. Test GET /data
    print("\n[4] Testing GET /data (Retrieve documents)...")
    status, body = make_request(f"{base_url}/data", method="GET")
    print(f"    Status: {status}")
    print(f"    Response: {body}")
    assert status == 200, f"Expected 200, got {status}"
    docs = json.loads(body)
    assert isinstance(docs, list), "Expected JSON array of documents"
    assert len(docs) > 0, "Expected at least 1 document"
    # Ensure _id is excluded as per requirement
    for doc in docs:
        assert "_id" not in doc, "Found '_id' field in response, should be excluded!"
    print("    --> PASS")

    # 5. Test Invalid Payload Validation (400)
    print("\n[5] Testing Validation on invalid POST /data...")
    status, body = make_request(f"{base_url}/data", method="POST", data="not-json", headers={"Content-Type": "text/plain"})
    print(f"    Status: {status}, Response: {body}")
    assert status == 400, f"Expected 400 Bad Request, got {status}"
    print("    --> PASS")

    print("\n" + "=" * 60)
    print("ALL API SMOKE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


def run_load_stress_test(base_url, duration, concurrency):
    print("\n" + "=" * 60)
    print(f"RUNNING HIGH TRAFFIC / CPU STRESS TEST FOR HPA")
    print(f"Target URL:    {base_url}/stress/cpu?duration=1")
    print(f"Duration:      {duration} seconds")
    print(f"Concurrency:   {concurrency} threads")
    print("=" * 60)
    print("Monitor HPA in a separate terminal: kubectl get hpa flask-hpa -n flask-demo -w\n")

    end_time = time.time() + duration
    total_requests = 0
    successful_requests = 0

    def worker():
        nonlocal total_requests, successful_requests
        while time.time() < end_time:
            status, _ = make_request(f"{base_url}/stress/cpu?duration=1", timeout=10)
            total_requests += 1
            if status == 200:
                successful_requests += 1

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker) for _ in range(concurrency)]
        concurrent.futures.wait(futures)

    elapsed = time.time() - start
    print(f"\nStress run completed in {elapsed:.2f}s")
    print(f"Total requests:      {total_requests}")
    print(f"Successful requests: {successful_requests}")
    print(f"Throughput:          {total_requests / elapsed:.2f} req/s")
    print("\nCheck current replicas: kubectl get deployment flask -n flask-demo")


def main():
    parser = argparse.ArgumentParser(description="Test Flask + MongoDB API on Kubernetes")
    parser.add_argument("--url", default="http://localhost:5000", help="Base URL of Flask service")
    parser.add_argument("--stress", action="store_true", help="Run CPU stress test to trigger HPA scaling")
    parser.add_argument("--duration", type=int, default=45, help="Stress test duration in seconds")
    parser.add_argument("--concurrency", type=int, default=8, help="Concurrent client threads for stress test")

    args = parser.parse_args()

    try:
        run_smoke_tests(args.url)
        if args.stress:
            run_load_stress_test(args.url, args.duration, args.concurrency)
    except AssertionError as e:
        print(f"\n[FAIL] Test assertion failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Could not connect to API: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
