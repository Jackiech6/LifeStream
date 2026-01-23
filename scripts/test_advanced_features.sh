#!/bin/bash
# Comprehensive test script for advanced features:
# - Speaker Diarization
# - Scene Detection
# - LLM Summarization
# - Meeting Detection

set -e

API_URL="${NEXT_PUBLIC_API_URL:-https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging}"

echo "========================================="
echo "LifeStream Advanced Features Test"
echo "========================================="
echo "API URL: $API_URL"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health Check
echo -e "${YELLOW}Test 1: Health Check${NC}"
HEALTH=$(curl -s "$API_URL/health")
if echo "$HEALTH" | grep -q "healthy"; then
    echo -e "${GREEN}   ✅ PASS: Health check successful${NC}"
else
    echo -e "${RED}   ❌ FAIL: Health check failed${NC}"
    exit 1
fi

# Test 2: Upload a test video and get job ID
echo ""
echo -e "${YELLOW}Test 2: Upload Test Video${NC}"
PRESIGNED_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/upload/presigned-url" \
    -H "Content-Type: application/json" \
    -d '{"filename":"test_advanced_features.mp4","file_size":5000000}')

JOB_ID=$(echo "$PRESIGNED_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_id', ''))" 2>/dev/null || echo "")
UPLOAD_URL=$(echo "$PRESIGNED_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('upload_url', ''))" 2>/dev/null || echo "")

if [ -z "$JOB_ID" ]; then
    echo -e "${RED}   ❌ FAIL: Could not get job ID${NC}"
    echo "   Response: $PRESIGNED_RESPONSE"
    exit 1
fi

echo -e "${GREEN}   ✅ PASS: Presigned URL generated${NC}"
echo "   Job ID: $JOB_ID"
echo ""
echo "   Note: For full test, upload a real video file to: $UPLOAD_URL"
echo "   Then confirm upload and wait for processing..."

# Test 3: Check for existing processed jobs
echo ""
echo -e "${YELLOW}Test 3: Check Existing Processed Jobs${NC}"
# Get list of jobs from RDS or S3 (simplified - check status endpoint)
STATUS_RESPONSE=$(curl -s "$API_URL/api/v1/status/$JOB_ID" 2>/dev/null || echo '{"status":"not_found"}')
STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")

if [ "$STATUS" = "completed" ]; then
    echo -e "${GREEN}   ✅ Found completed job: $JOB_ID${NC}"
    
    # Test 4: Get Summary and verify advanced features
    echo ""
    echo -e "${YELLOW}Test 4: Verify Advanced Features in Summary${NC}"
    SUMMARY_RESPONSE=$(curl -s "$API_URL/api/v1/summary/$JOB_ID")
    
    # Check for meeting detection
    if echo "$SUMMARY_RESPONSE" | grep -qi "meeting\|non-meeting\|Context Type"; then
        echo -e "${GREEN}   ✅ Meeting detection present in summary${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Meeting detection not found (may be in markdown)${NC}"
    fi
    
    # Check for participants (diarization)
    if echo "$SUMMARY_RESPONSE" | grep -qi "participant\|speaker"; then
        echo -e "${GREEN}   ✅ Speaker diarization data present${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Speaker diarization data not found${NC}"
    fi
    
    # Check for scene detection
    if echo "$SUMMARY_RESPONSE" | grep -qi "scene\|keyframe"; then
        echo -e "${GREEN}   ✅ Scene detection data present${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Scene detection data not found${NC}"
    fi
    
    # Check for LLM summarization (non-generic activity)
    if echo "$SUMMARY_RESPONSE" | grep -qi "Activity: Activity"; then
        echo -e "${RED}   ❌ FAIL: Generic 'Activity' found (summarization issue)${NC}"
    else
        echo -e "${GREEN}   ✅ LLM summarization working (no generic 'Activity')${NC}"
    fi
    
    # Check for proper time format (HH:MM:SS)
    if echo "$SUMMARY_RESPONSE" | grep -qE "[0-9]{2}:[0-9]{2}:[0-9]{2}"; then
        echo -e "${GREEN}   ✅ Time format correct (HH:MM:SS)${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Time format may not be HH:MM:SS${NC}"
    fi
    
else
    echo -e "${YELLOW}   ⚠️  Job $JOB_ID status: $STATUS (not completed yet)${NC}"
    echo "   To test advanced features:"
    echo "   1. Upload a video file to the presigned URL"
    echo "   2. Confirm upload via API"
    echo "   3. Wait for processing to complete"
    echo "   4. Re-run this script"
fi

# Test 5: Query endpoint (semantic search)
echo ""
echo -e "${YELLOW}Test 5: Semantic Search (RAG)${NC}"
QUERY_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/query" \
    -H "Content-Type: application/json" \
    -d '{"query": "test query for advanced features", "top_k": 3}')

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/v1/query" \
    -H "Content-Type: application/json" \
    -d '{"query": "test", "top_k": 3}')

if [ "$HTTP_CODE" = "200" ]; then
    RESULT_COUNT=$(echo "$QUERY_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('results', [])))" 2>/dev/null || echo "0")
    echo -e "${GREEN}   ✅ Query endpoint working (HTTP 200)${NC}"
    echo "   Results found: $RESULT_COUNT"
else
    echo -e "${RED}   ❌ FAIL: Query endpoint returned HTTP $HTTP_CODE${NC}"
fi

echo ""
echo "========================================="
echo -e "${GREEN}Advanced Features Test Complete${NC}"
echo "========================================="
echo ""
echo "Next steps for full verification:"
echo "  1. Upload a real video with multiple speakers (meeting)"
echo "  2. Upload a tutorial/lecture video (non-meeting)"
echo "  3. Verify summaries show:"
echo "     - Proper speaker identification (not 'unknown: unknown')"
echo "     - Meeting vs Non-Meeting context"
echo "     - Scene changes detected"
echo "     - Specific activities (not generic 'Activity')"
echo "     - Proper time format (HH:MM:SS)"
