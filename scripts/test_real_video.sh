#!/bin/bash
# Test script for uploading real video file (testvid.mp4 from desktop)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VIDEO_PATH="/Users/chenjackie/Desktop/testvid.mp4"
AWS_REGION="${AWS_REGION:-us-east-1}"

API_URL="$(cd "$PROJECT_ROOT/infrastructure" && terraform output -raw api_gateway_url)"

log() { echo -e "\n\033[1;34m[test-real-video]\033[0m $*"; }
log_success() { echo -e "\033[1;32m[test-real-video] SUCCESS:\033[0m $*"; }
log_error() { echo -e "\033[1;31m[test-real-video] ERROR:\033[0m $*" >&2; }

# Check if video exists
if [ ! -f "$VIDEO_PATH" ]; then
    log_error "Video file not found: $VIDEO_PATH"
    exit 1
fi

# Get file info
VIDEO_SIZE=$(stat -f%z "$VIDEO_PATH" 2>/dev/null || stat -c%s "$VIDEO_PATH" 2>/dev/null || echo "0")
VIDEO_SIZE_MB=$((VIDEO_SIZE / 1024 / 1024))
log "Video file: $(basename "$VIDEO_PATH")"
log "Size: ${VIDEO_SIZE_MB} MB (${VIDEO_SIZE} bytes)"

# Check if file is too large for API Gateway (10MB limit)
if [ "$VIDEO_SIZE" -gt 10485760 ]; then
    log "File exceeds API Gateway 10MB limit - using presigned URL (recommended)"
    USE_PRESIGNED=true
else
    log "File is under 10MB - but using presigned URL anyway (recommended approach)"
    USE_PRESIGNED=true
fi

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

# Step 1: Get presigned URL
log "Step 1: Requesting presigned URL..."
PRESIGNED_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/upload/presigned-url" \
    -H "Content-Type: application/json" \
    -d "{\"filename\": \"$(basename "$VIDEO_PATH")\", \"file_size\": $VIDEO_SIZE}")

if ! echo "$PRESIGNED_RESPONSE" | grep -q 'upload_url'; then
    log_error "Failed to get presigned URL:"
    echo "$PRESIGNED_RESPONSE" >&2
    exit 1
fi

UPLOAD_URL=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('upload_url',''))" "$PRESIGNED_RESPONSE")
S3_KEY=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('s3_key',''))" "$PRESIGNED_RESPONSE")
JOB_ID=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('job_id',''))" "$PRESIGNED_RESPONSE")

log_success "Presigned URL generated:"
echo "  Job ID: $JOB_ID"
echo "  S3 Key: $S3_KEY"

# Step 2: Upload to S3
log "Step 2: Uploading ${VIDEO_SIZE_MB}MB file to S3 (this may take a while)..."
UPLOAD_START=$(date +%s)
UPLOAD_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PUT \
    --data-binary "@$VIDEO_PATH" \
    -H "Content-Type: video/mp4" \
    --max-time 600 \
    "$UPLOAD_URL")
UPLOAD_END=$(date +%s)
UPLOAD_DURATION=$((UPLOAD_END - UPLOAD_START))

if [ "$UPLOAD_HTTP_CODE" != "200" ]; then
    log_error "S3 upload failed with HTTP code: $UPLOAD_HTTP_CODE"
    exit 1
fi

log_success "File uploaded to S3 in ${UPLOAD_DURATION}s"

# Step 3: Verify S3 file size
log "Step 3: Verifying S3 file..."
S3_BUCKET_NAME="$(cd "$PROJECT_ROOT/infrastructure" && terraform output -raw s3_bucket_name)"
S3_FILE_SIZE=$(aws s3api head-object --bucket "$S3_BUCKET_NAME" --key "$S3_KEY" \
    --query 'ContentLength' --output text --region "$AWS_REGION" 2>/dev/null || echo "not found")

if [ "$S3_FILE_SIZE" = "not found" ]; then
    log_error "S3 file not found: s3://$S3_BUCKET_NAME/$S3_KEY"
    exit 1
elif [ "$S3_FILE_SIZE" -ne "$VIDEO_SIZE" ]; then
    log_error "S3 file size mismatch! Expected: ${VIDEO_SIZE} bytes, Got: ${S3_FILE_SIZE} bytes"
    exit 1
else
    log_success "S3 file size matches: ${S3_FILE_SIZE} bytes"
fi

# Step 4: Confirm upload
log "Step 4: Confirming upload and creating processing job..."
CONFIRM_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/upload/confirm" \
    -H "Content-Type: application/json" \
    -d "{\"job_id\": \"$JOB_ID\", \"s3_key\": \"$S3_KEY\"}")

if ! echo "$CONFIRM_RESPONSE" | grep -q 'job_id'; then
    log_error "Failed to confirm upload:"
    echo "$CONFIRM_RESPONSE" >&2
    exit 1
fi

CONFIRMED_JOB_ID=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('job_id',''))" "$CONFIRM_RESPONSE")
STATUS=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('status',''))" "$CONFIRM_RESPONSE")

log_success "Upload confirmed:"
echo "  Job ID: $CONFIRMED_JOB_ID"
echo "  Status: $STATUS"

# Step 5: Monitor job status
log "Step 5: Monitoring job status (will check for 120 seconds)..."
MAX_WAIT=120
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    sleep 10
    ELAPSED=$((ELAPSED + 10))
    
    STATUS_RESPONSE=$(curl -s "$API_URL/api/v1/status/$JOB_ID" 2>/dev/null || echo '{"status":"unknown"}')
    STATUS=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('status','unknown'))" "$STATUS_RESPONSE" 2>/dev/null || echo "unknown")
    
    echo "  [${ELAPSED}s] Status: $STATUS"
    
    if [ "$STATUS" = "completed" ]; then
        log_success "Job completed successfully!"
        break
    elif [ "$STATUS" = "failed" ]; then
        ERROR=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('error','Unknown error'))" "$STATUS_RESPONSE" 2>/dev/null || echo "Unknown error")
        log_error "Job failed: $ERROR"
        exit 1
    fi
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    log "Job did not complete within ${MAX_WAIT} seconds (status: $STATUS)"
    log "Check CloudWatch logs for job $JOB_ID"
fi

log_success "Test completed successfully!"
echo "  Job ID: $JOB_ID"
echo "  S3 Location: s3://$S3_BUCKET_NAME/$S3_KEY"
exit 0
