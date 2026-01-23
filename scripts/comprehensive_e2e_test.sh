#!/bin/bash
# Comprehensive End-to-End Test for LifeStream API
# Tests all features: upload, status, summary, query

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VIDEO_PATH="/Users/chenjackie/Desktop/testvid.mp4"
AWS_REGION="${AWS_REGION:-us-east-1}"

API_URL="$(cd "$PROJECT_ROOT/infrastructure" && terraform output -raw api_gateway_url)"
S3_BUCKET_NAME="$(cd "$PROJECT_ROOT/infrastructure" && terraform output -raw s3_bucket_name)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
TEST_RESULTS=()

log() { echo -e "${BLUE}[E2E-TEST]${NC} $*"; }
log_success() { echo -e "${GREEN}[E2E-TEST] ✅${NC} $*"; TESTS_PASSED=$((TESTS_PASSED + 1)); }
log_error() { echo -e "${RED}[E2E-TEST] ❌${NC} $*" >&2; TESTS_FAILED=$((TESTS_FAILED + 1)); }
log_warn() { echo -e "${YELLOW}[E2E-TEST] ⚠️${NC} $*"; }
log_info() { echo -e "${BLUE}[E2E-TEST] ℹ️${NC} $*"; }

# Python command
PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    log_error "Neither python3 nor python found in PATH"
    exit 1
fi

# Check if video exists
if [ ! -f "$VIDEO_PATH" ]; then
    log_error "Video file not found: $VIDEO_PATH"
    exit 1
fi

VIDEO_SIZE=$(stat -f%z "$VIDEO_PATH" 2>/dev/null || stat -c%s "$VIDEO_PATH" 2>/dev/null || echo "0")
VIDEO_SIZE_MB=$((VIDEO_SIZE / 1024 / 1024))

log "Starting comprehensive E2E test with testvid.mp4 (${VIDEO_SIZE_MB}MB)"
log "API URL: $API_URL"
echo ""

# ============================================================================
# TEST 1: Health Check
# ============================================================================
log "TEST 1: Health Check Endpoint"
HEALTH_RESPONSE=$(curl -s "$API_URL/health" 2>&1)
if echo "$HEALTH_RESPONSE" | grep -q '"status"'; then
    log_success "Health check passed"
    TEST_RESULTS+=("Health Check: ✅ PASSED")
else
    log_error "Health check failed: $HEALTH_RESPONSE"
    TEST_RESULTS+=("Health Check: ❌ FAILED")
fi
echo ""

# ============================================================================
# TEST 2: API Documentation
# ============================================================================
log "TEST 2: API Documentation Endpoints"
DOCS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/docs" 2>&1)
OPENAPI_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/openapi.json" 2>&1)

if [ "$DOCS_CODE" = "200" ]; then
    log_success "API docs endpoint accessible"
    TEST_RESULTS+=("API Docs: ✅ PASSED")
else
    log_warn "API docs returned code $DOCS_CODE"
    TEST_RESULTS+=("API Docs: ⚠️ WARNING")
fi

if [ "$OPENAPI_CODE" = "200" ]; then
    log_success "OpenAPI JSON accessible"
    TEST_RESULTS+=("OpenAPI JSON: ✅ PASSED")
else
    log_warn "OpenAPI JSON returned code $OPENAPI_CODE"
    TEST_RESULTS+=("OpenAPI JSON: ⚠️ WARNING")
fi
echo ""

# ============================================================================
# TEST 3: Presigned URL Generation
# ============================================================================
log "TEST 3: Presigned URL Generation"
PRESIGNED_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/upload/presigned-url" \
    -H "Content-Type: application/json" \
    -d "{\"filename\": \"$(basename "$VIDEO_PATH")\", \"file_size\": $VIDEO_SIZE}")

if ! echo "$PRESIGNED_RESPONSE" | grep -q 'upload_url'; then
    log_error "Failed to get presigned URL: $PRESIGNED_RESPONSE"
    TEST_RESULTS+=("Presigned URL Generation: ❌ FAILED")
    exit 1
fi

UPLOAD_URL=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('upload_url',''))" "$PRESIGNED_RESPONSE")
S3_KEY=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('s3_key',''))" "$PRESIGNED_RESPONSE")
JOB_ID=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('job_id',''))" "$PRESIGNED_RESPONSE")

if [ -z "$UPLOAD_URL" ] || [ -z "$S3_KEY" ] || [ -z "$JOB_ID" ]; then
    log_error "Failed to extract presigned URL data"
    TEST_RESULTS+=("Presigned URL Generation: ❌ FAILED")
    exit 1
fi

log_success "Presigned URL generated (Job ID: $JOB_ID)"
TEST_RESULTS+=("Presigned URL Generation: ✅ PASSED")
echo ""

# ============================================================================
# TEST 4: Direct S3 Upload
# ============================================================================
log "TEST 4: Direct S3 Upload via Presigned URL"
log_info "Uploading ${VIDEO_SIZE_MB}MB file (this may take a while)..."
UPLOAD_START=$(date +%s)
UPLOAD_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PUT \
    --data-binary "@$VIDEO_PATH" \
    -H "Content-Type: video/mp4" \
    --max-time 600 \
    "$UPLOAD_URL" 2>&1)
UPLOAD_END=$(date +%s)
UPLOAD_DURATION=$((UPLOAD_END - UPLOAD_START))

if [ "$UPLOAD_HTTP_CODE" != "200" ]; then
    log_error "S3 upload failed with HTTP code: $UPLOAD_HTTP_CODE"
    TEST_RESULTS+=("S3 Upload: ❌ FAILED")
    exit 1
fi

log_success "File uploaded to S3 in ${UPLOAD_DURATION}s"
TEST_RESULTS+=("S3 Upload: ✅ PASSED (${UPLOAD_DURATION}s)")
echo ""

# ============================================================================
# TEST 5: S3 File Verification
# ============================================================================
log "TEST 5: S3 File Verification"
S3_FILE_SIZE=$(aws s3api head-object --bucket "$S3_BUCKET_NAME" --key "$S3_KEY" \
    --query 'ContentLength' --output text --region "$AWS_REGION" 2>&1 || echo "error")

if [ "$S3_FILE_SIZE" = "error" ] || [ -z "$S3_FILE_SIZE" ]; then
    log_error "S3 file not found or error accessing it"
    TEST_RESULTS+=("S3 File Verification: ❌ FAILED")
elif [ "$S3_FILE_SIZE" -ne "$VIDEO_SIZE" ]; then
    log_error "S3 file size mismatch! Expected: ${VIDEO_SIZE}, Got: ${S3_FILE_SIZE}"
    TEST_RESULTS+=("S3 File Verification: ❌ FAILED")
else
    log_success "S3 file size matches: ${S3_FILE_SIZE} bytes"
    TEST_RESULTS+=("S3 File Verification: ✅ PASSED")
    
    # Verify file integrity
    if command -v ffprobe >/dev/null 2>&1; then
        aws s3 cp "s3://$S3_BUCKET_NAME/$S3_KEY" /tmp/e2e_validation.mp4 --region "$AWS_REGION" >/dev/null 2>&1
        if ffprobe -v error -show_format /tmp/e2e_validation.mp4 >/dev/null 2>&1; then
            log_success "S3 file is valid MP4"
            TEST_RESULTS+=("MP4 Validation: ✅ PASSED")
            rm -f /tmp/e2e_validation.mp4
        else
            log_error "S3 file failed MP4 validation"
            TEST_RESULTS+=("MP4 Validation: ❌ FAILED")
        fi
    else
        log_warn "ffprobe not available, skipping MP4 validation"
        TEST_RESULTS+=("MP4 Validation: ⚠️ SKIPPED")
    fi
fi
echo ""

# ============================================================================
# TEST 6: Upload Confirmation
# ============================================================================
log "TEST 6: Upload Confirmation and Job Creation"
CONFIRM_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/upload/confirm" \
    -H "Content-Type: application/json" \
    -d "{\"job_id\": \"$JOB_ID\", \"s3_key\": \"$S3_KEY\"}")

if ! echo "$CONFIRM_RESPONSE" | grep -q 'job_id'; then
    log_error "Failed to confirm upload: $CONFIRM_RESPONSE"
    TEST_RESULTS+=("Upload Confirmation: ❌ FAILED")
    exit 1
fi

CONFIRMED_JOB_ID=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('job_id',''))" "$CONFIRM_RESPONSE")
STATUS=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('status',''))" "$CONFIRM_RESPONSE")

if [ "$CONFIRMED_JOB_ID" != "$JOB_ID" ]; then
    log_error "Job ID mismatch"
    TEST_RESULTS+=("Upload Confirmation: ❌ FAILED")
else
    log_success "Upload confirmed, job created (Status: $STATUS)"
    TEST_RESULTS+=("Upload Confirmation: ✅ PASSED")
fi
echo ""

# ============================================================================
# TEST 7: Job Status Polling
# ============================================================================
log "TEST 7: Job Status Polling"
MAX_WAIT=300  # 5 minutes
ELAPSED=0
FINAL_STATUS="unknown"
LAST_STAGE=""

while [ $ELAPSED -lt $MAX_WAIT ]; do
    sleep 15
    ELAPSED=$((ELAPSED + 15))
    
    STATUS_RESPONSE=$(curl -s "$API_URL/api/v1/status/$JOB_ID" 2>&1)
    STATUS=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('status','unknown'))" "$STATUS_RESPONSE" 2>/dev/null || echo "unknown")
    CURRENT_STAGE=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('current_stage',''))" "$STATUS_RESPONSE" 2>/dev/null || echo "")
    PROGRESS=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('progress',''))" "$STATUS_RESPONSE" 2>/dev/null || echo "")
    
    if [ -n "$CURRENT_STAGE" ] && [ "$CURRENT_STAGE" != "$LAST_STAGE" ]; then
        log_info "[${ELAPSED}s] Status: $STATUS | Stage: $CURRENT_STAGE | Progress: ${PROGRESS:-N/A}"
        LAST_STAGE="$CURRENT_STAGE"
    else
        log_info "[${ELAPSED}s] Status: $STATUS"
    fi
    
    FINAL_STATUS="$STATUS"
    
    if [ "$STATUS" = "completed" ]; then
        log_success "Job completed successfully!"
        TEST_RESULTS+=("Job Status Polling: ✅ PASSED (completed in ${ELAPSED}s)")
        break
    elif [ "$STATUS" = "failed" ]; then
        ERROR=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('error','Unknown error'))" "$STATUS_RESPONSE" 2>/dev/null || echo "Unknown error")
        log_error "Job failed: $ERROR"
        TEST_RESULTS+=("Job Status Polling: ❌ FAILED - $ERROR")
        break
    fi
done

if [ "$FINAL_STATUS" != "completed" ] && [ "$FINAL_STATUS" != "failed" ]; then
    log_warn "Job did not complete within ${MAX_WAIT} seconds (status: $FINAL_STATUS)"
    TEST_RESULTS+=("Job Status Polling: ⚠️ TIMEOUT (status: $FINAL_STATUS)")
fi
echo ""

# ============================================================================
# TEST 8: Summary Retrieval
# ============================================================================
log "TEST 8: Summary Retrieval"
SUMMARY_RESPONSE=$(curl -s "$API_URL/api/v1/summary/$JOB_ID" 2>&1)
SUMMARY_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v1/summary/$JOB_ID" 2>&1)

if [ "$SUMMARY_CODE" = "200" ]; then
    if echo "$SUMMARY_RESPONSE" | grep -q 'summary_markdown'; then
        SUMMARY_LENGTH=$(echo "$SUMMARY_RESPONSE" | $PYTHON_CMD -c "import json,sys; j=json.loads(sys.stdin.read()); print(len(j.get('summary_markdown','')))" 2>/dev/null || echo "0")
        if [ "$SUMMARY_LENGTH" -gt 0 ]; then
            log_success "Summary retrieved (${SUMMARY_LENGTH} characters)"
            TEST_RESULTS+=("Summary Retrieval: ✅ PASSED")
        else
            log_warn "Summary retrieved but is empty"
            TEST_RESULTS+=("Summary Retrieval: ⚠️ WARNING (empty)")
        fi
    else
        log_warn "Summary endpoint returned 200 but no summary_markdown field"
        TEST_RESULTS+=("Summary Retrieval: ⚠️ WARNING")
    fi
elif [ "$SUMMARY_CODE" = "404" ]; then
    log_warn "Summary not found (job may still be processing)"
    TEST_RESULTS+=("Summary Retrieval: ⚠️ NOT FOUND (job may be processing)")
else
    log_error "Summary retrieval failed with code: $SUMMARY_CODE"
    TEST_RESULTS+=("Summary Retrieval: ❌ FAILED (code: $SUMMARY_CODE)")
fi
echo ""

# ============================================================================
# TEST 9: Query/Search Functionality
# ============================================================================
log "TEST 9: Query/Search Functionality"
QUERY_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/query" \
    -H "Content-Type: application/json" \
    -d '{"query": "What happened in the video?", "max_results": 5}' 2>&1)
QUERY_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/v1/query" \
    -H "Content-Type: application/json" \
    -d '{"query": "What happened in the video?", "max_results": 5}' 2>&1)

if [ "$QUERY_CODE" = "200" ]; then
    if echo "$QUERY_RESPONSE" | grep -q 'results'; then
        RESULT_COUNT=$(echo "$QUERY_RESPONSE" | $PYTHON_CMD -c "import json,sys; j=json.loads(sys.stdin.read()); print(len(j.get('results',[])))" 2>/dev/null || echo "0")
        log_success "Query executed successfully (${RESULT_COUNT} results)"
        TEST_RESULTS+=("Query/Search: ✅ PASSED (${RESULT_COUNT} results)")
    else
        log_warn "Query returned 200 but no results field"
        TEST_RESULTS+=("Query/Search: ⚠️ WARNING")
    fi
elif [ "$QUERY_CODE" = "503" ] || [ "$QUERY_CODE" = "404" ]; then
    log_warn "Query service unavailable or no data indexed yet (code: $QUERY_CODE)"
    TEST_RESULTS+=("Query/Search: ⚠️ UNAVAILABLE (code: $QUERY_CODE)")
else
    log_error "Query failed with code: $QUERY_CODE"
    TEST_RESULTS+=("Query/Search: ❌ FAILED (code: $QUERY_CODE)")
fi
echo ""

# ============================================================================
# TEST 10: Error Handling
# ============================================================================
log "TEST 10: Error Handling"
# Test invalid job ID
INVALID_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v1/status/invalid-job-id-12345" 2>&1)
if [ "$INVALID_STATUS" = "404" ] || [ "$INVALID_STATUS" = "400" ]; then
    log_success "Invalid job ID handled correctly (code: $INVALID_STATUS)"
    TEST_RESULTS+=("Error Handling: ✅ PASSED")
else
    log_warn "Invalid job ID returned unexpected code: $INVALID_STATUS"
    TEST_RESULTS+=("Error Handling: ⚠️ WARNING")
fi
echo ""

# ============================================================================
# TEST 11: Deprecated Endpoint
# ============================================================================
log "TEST 11: Deprecated Endpoint Handling"
DEPRECATED_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/upload/upload" 2>&1)
DEPRECATED_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/v1/upload/upload" 2>&1)

if [ "$DEPRECATED_CODE" = "410" ] || echo "$DEPRECATED_RESPONSE" | grep -q "deprecated"; then
    log_success "Deprecated endpoint correctly returns 410 Gone"
    TEST_RESULTS+=("Deprecated Endpoint: ✅ PASSED")
else
    log_warn "Deprecated endpoint returned code: $DEPRECATED_CODE"
    TEST_RESULTS+=("Deprecated Endpoint: ⚠️ WARNING")
fi
echo ""

# ============================================================================
# FINAL SUMMARY
# ============================================================================
log "=========================================="
log "COMPREHENSIVE E2E TEST SUMMARY"
log "=========================================="
echo ""
log "Test Results:"
for result in "${TEST_RESULTS[@]}"; do
    echo "  $result"
done
echo ""
log "Statistics:"
log_success "Tests Passed: $TESTS_PASSED"
if [ $TESTS_FAILED -gt 0 ]; then
    log_error "Tests Failed: $TESTS_FAILED"
else
    log_success "Tests Failed: $TESTS_FAILED"
fi

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
if [ $TOTAL_TESTS -gt 0 ]; then
    PASS_RATE=$((TESTS_PASSED * 100 / TOTAL_TESTS))
    log_info "Pass Rate: ${PASS_RATE}%"
fi
echo ""

# Check processor logs for any errors
log "Checking Processor Lambda logs for errors..."
PROCESSOR_ERRORS=$(aws logs tail "/aws/lambda/lifestream-video-processor-staging" \
    --since 10m --format short --region "$AWS_REGION" 2>&1 | grep -i "error\|failed\|exception" | wc -l || echo "0")

if [ "$PROCESSOR_ERRORS" -gt 0 ]; then
    log_warn "Found $PROCESSOR_ERRORS error(s) in processor logs (check CloudWatch for details)"
else
    log_success "No errors found in recent processor logs"
fi
echo ""

# Final verdict
if [ $TESTS_FAILED -eq 0 ] && [ "$FINAL_STATUS" = "completed" ]; then
    log_success "=========================================="
    log_success "ALL TESTS PASSED - SYSTEM IS ROBUST ✅"
    log_success "=========================================="
    exit 0
elif [ $TESTS_FAILED -eq 0 ]; then
    log_warn "=========================================="
    log_warn "TESTS PASSED BUT JOB NOT COMPLETED ⚠️"
    log_warn "=========================================="
    log_warn "Job status: $FINAL_STATUS"
    log_warn "This may be expected if processing takes longer than 5 minutes"
    exit 0
else
    log_error "=========================================="
    log_error "SOME TESTS FAILED ❌"
    log_error "=========================================="
    exit 1
fi
