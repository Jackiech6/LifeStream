#!/bin/bash
# Test script to simulate full user flow
# This tests the API endpoints that the frontend uses

set -e

API_URL="${NEXT_PUBLIC_API_URL:-https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging}"

echo "========================================="
echo "LifeStream Frontend User Flow Test"
echo "========================================="
echo "API URL: $API_URL"
echo ""

# Test 1: Health Check
echo "✅ Test 1: Health Check"
HEALTH=$(curl -s "$API_URL/health")
if echo "$HEALTH" | grep -q "healthy"; then
    echo "   PASS: Health check successful"
else
    echo "   FAIL: Health check failed"
    exit 1
fi

# Test 2: Generate Presigned URL
echo ""
echo "✅ Test 2: Generate Presigned URL"
PRESIGNED_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/upload/presigned-url" \
    -H "Content-Type: application/json" \
    -H "Origin: http://localhost:3000" \
    -d '{"filename":"test-flow.mp4","file_size":1024000}')

if echo "$PRESIGNED_RESPONSE" | grep -q "upload_url"; then
    JOB_ID=$(echo "$PRESIGNED_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])" 2>/dev/null || echo "")
    S3_KEY=$(echo "$PRESIGNED_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['s3_key'])" 2>/dev/null || echo "")
    echo "   PASS: Presigned URL generated"
    echo "   Job ID: $JOB_ID"
    echo "   S3 Key: $S3_KEY"
else
    echo "   FAIL: Presigned URL generation failed"
    echo "   Response: $PRESIGNED_RESPONSE"
    exit 1
fi

# Test 3: Check CORS
echo ""
echo "✅ Test 3: CORS Headers"
CORS_HEADERS=$(curl -s -I -X OPTIONS "$API_URL/api/v1/query" \
    -H "Origin: http://localhost:3000" \
    -H "Access-Control-Request-Method: POST" | grep -i "access-control" || echo "")

if echo "$CORS_HEADERS" | grep -q "access-control-allow-origin"; then
    echo "   PASS: CORS headers present"
    echo "$CORS_HEADERS" | sed 's/^/   /'
else
    echo "   WARN: CORS headers not found (may still work)"
fi

# Test 4: Query Endpoint
echo ""
echo "✅ Test 4: Query Endpoint (Chat)"
QUERY_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/query" \
    -H "Content-Type: application/json" \
    -H "Origin: http://localhost:3000" \
    -d '{"query": "test query", "top_k": 5}')

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/v1/query" \
    -H "Content-Type: application/json" \
    -H "Origin: http://localhost:3000" \
    -d '{"query": "test query", "top_k": 5}')

if [ "$HTTP_CODE" = "200" ]; then
    echo "   PASS: Query endpoint returns HTTP 200"
    if echo "$QUERY_RESPONSE" | grep -q "results"; then
        RESULT_COUNT=$(echo "$QUERY_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('results', [])))" 2>/dev/null || echo "0")
        echo "   Results found: $RESULT_COUNT"
    fi
else
    echo "   FAIL: Query endpoint returned HTTP $HTTP_CODE"
    echo "   Response: $QUERY_RESPONSE"
    exit 1
fi

# Test 5: Status Endpoint (using existing job)
echo ""
echo "✅ Test 5: Status Endpoint"
EXISTING_JOB="00ac9c5b-1cfb-4ac9-ab6c-dd9712ae3001"
STATUS_RESPONSE=$(curl -s "$API_URL/api/v1/status/$EXISTING_JOB" \
    -H "Origin: http://localhost:3000")

if echo "$STATUS_RESPONSE" | grep -q "job_id"; then
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
    echo "   PASS: Status endpoint working"
    echo "   Job Status: $STATUS"
else
    echo "   FAIL: Status endpoint failed"
    echo "   Response: $STATUS_RESPONSE"
    exit 1
fi

# Test 6: Summary Endpoint
echo ""
echo "✅ Test 6: Summary Endpoint"
SUMMARY_RESPONSE=$(curl -s "$API_URL/api/v1/summary/$EXISTING_JOB" \
    -H "Origin: http://localhost:3000")

if echo "$SUMMARY_RESPONSE" | grep -q "summary_markdown"; then
    echo "   PASS: Summary endpoint working"
    MARKDOWN_LENGTH=$(echo "$SUMMARY_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('summary_markdown', '')))" 2>/dev/null || echo "0")
    echo "   Summary length: $MARKDOWN_LENGTH characters"
else
    echo "   FAIL: Summary endpoint failed"
    echo "   Response: $SUMMARY_RESPONSE"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ All API Endpoint Tests Passed!"
echo "========================================="
echo ""
echo "Frontend is ready for manual testing:"
echo "  1. Open http://localhost:3000"
echo "  2. Upload a video file"
echo "  3. Monitor job status"
echo "  4. View summary when complete"
echo "  5. Test chat/query interface"
echo ""
