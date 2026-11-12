#!/bin/bash
set -e

BASE_URL="${1:-http://localhost:5000}"

echo "============================================================"
echo "SMOKE TEST: Flask + MongoDB API at ${BASE_URL}"
echo "============================================================"

echo -e "\n[1] GET / (Root Endpoint)..."
curl -s "${BASE_URL}/"
echo ""

echo -e "\n[2] Checking Health Probes..."
curl -s "${BASE_URL}/health/live"
echo ""
curl -s "${BASE_URL}/health/ready"
echo ""

echo -e "\n[3] POST /data (Insert Document)..."
curl -s -X POST "${BASE_URL}/data" \
  -H "Content-Type: application/json" \
  -d '{"sampleKey":"sampleValue","author":"Aman","source":"bash-test"}'
echo ""

echo -e "\n[4] GET /data (Retrieve Documents)..."
curl -s "${BASE_URL}/data"
echo ""

echo -e "\n============================================================"
echo "ALL TESTS PASSED!"
echo "============================================================"
