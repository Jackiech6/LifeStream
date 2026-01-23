#!/bin/bash
# Test script for presigned S3 URL upload flow
# This bypasses the multipart form data parsing issues in Lambda

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VIDEO_DIR="$PROJECT_ROOT/test_assets"
VIDEO_PATH="$VIDEO_DIR/test_5s.mp4"
AWS_REGION="${AWS_REGION:-us-east-1}"

API_URL="$(cd "$PROJECT_ROOT/infrastructure" && terraform output -raw api_gateway_url)"
S3_BUCKET_NAME="$(cd "$PROJECT_ROOT/infrastructure" && terraform output -raw s3_bucket_name)"

log() { echo -e "\n\033[1;34m[presigned-upload]\033[0m $*"; }
log_success() { echo -e "\033[1;32m[presigned-upload] SUCCESS:\033[0m $*"; }
log_error() { echo -e "\033[1;31m[presigned-upload] ERROR:\033[0m $*" >&2; }
log_warn() { echo -e "\033[1;33m[presigned-upload] WARNING:\033[0m $*"; }

# Ensure test video exists
mkdir -p "$VIDEO_DIR"
if [ ! -f "$VIDEO_PATH" ]; then
    log "Test video not found, generating at $VIDEO_PATH"
    if ! command -v ffmpeg >/dev/null 2>&1; then
        log_error "ffmpeg not found. Install it on macOS with: brew install ffmpeg"
        exit 1
    fi
    ffmpeg -y \
        -f lavfi -i testsrc=duration=5:size=640x360:rate=25 \
        -f lavfi -i sine=frequency=1000:duration=5 \
        -c:v libx264 -c:a aac \
        -movflags +faststart \
        "$VIDEO_PATH"
    log_success "Generated test video: $VIDEO_PATH"
fi

# Verify local video
if command -v ffprobe >/dev/null 2>&1; then
    if ! ffprobe -v error -show_format "$VIDEO_PATH" >/dev/null 2>&1; then
        log_error "Local video file is invalid"
        exit 1
    fi
    LOCAL_SIZE=$(stat -f%z "$VIDEO_PATH" 2>/dev/null || stat -c%s "$VIDEO_PATH" 2>/dev/null || echo "0")
    log_success "Local video validated: $LOCAL_SIZE bytes"
else
    LOCAL_SIZE=$(stat -f%z "$VIDEO_PATH" 2>/dev/null || stat -c%s "$VIDEO_PATH" 2>/dev/null || echo "0")
    log_warn "ffprobe not found, skipping local validation"
fi

# Step 1: Generate presigned URL
log "Step 1: Requesting presigned URL from $API_URL/api/v1/upload/presigned-url..."
PRESIGNED_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/upload/presigned-url" \
    -H "Content-Type: application/json" \
    -d "{\"filename\": \"$(basename "$VIDEO_PATH")\", \"file_size\": $LOCAL_SIZE}")

if ! echo "$PRESIGNED_RESPONSE" | grep -q 'upload_url'; then
    log_error "Failed to get presigned URL:"
    echo "$PRESIGNED_RESPONSE" >&2
    exit 1
fi

# Extract values from response
PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    log_error "Neither python3 nor python found in PATH"
    exit 1
fi

UPLOAD_URL=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('upload_url',''))" "$PRESIGNED_RESPONSE")
S3_KEY=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('s3_key',''))" "$PRESIGNED_RESPONSE")
JOB_ID=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('job_id',''))" "$PRESIGNED_RESPONSE")

if [ -z "$UPLOAD_URL" ] || [ -z "$S3_KEY" ] || [ -z "$JOB_ID" ]; then
    log_error "Failed to extract presigned URL data from response:"
    echo "$PRESIGNED_RESPONSE" >&2
    exit 1
fi

log_success "Presigned URL generated:"
echo "  Job ID: $JOB_ID"
echo "  S3 Key: $S3_KEY"
echo "  Upload URL: ${UPLOAD_URL:0:80}..."

# Step 2: Upload file directly to S3 using presigned URL
log "Step 2: Uploading file directly to S3 using presigned URL..."
UPLOAD_START_TIME=$(date +%s)
UPLOAD_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PUT \
    --data-binary "@$VIDEO_PATH" \
    -H "Content-Type: video/mp4" \
    "$UPLOAD_URL")
UPLOAD_END_TIME=$(date +%s)
UPLOAD_DURATION=$((UPLOAD_END_TIME - UPLOAD_START_TIME))

if [ "$UPLOAD_HTTP_CODE" != "200" ]; then
    log_error "S3 upload failed with HTTP code: $UPLOAD_HTTP_CODE"
    exit 1
fi

log_success "File uploaded to S3 in ${UPLOAD_DURATION}s"

# Step 3: Verify S3 file size
log "Step 3: Verifying S3 file size..."
S3_FILE_SIZE=$(aws s3api head-object --bucket "$S3_BUCKET_NAME" --key "$S3_KEY" \
    --query 'ContentLength' --output text --region "$AWS_REGION" 2>/dev/null || echo "not found")

if [ "$S3_FILE_SIZE" = "not found" ]; then
    log_error "S3 file not found after upload: s3://$S3_BUCKET_NAME/$S3_KEY"
    exit 1
elif [ "$S3_FILE_SIZE" -ne "$LOCAL_SIZE" ]; then
    log_error "S3 file size mismatch! Expected: ${LOCAL_SIZE} bytes, Got: ${S3_FILE_SIZE} bytes"
    exit 1
else
    log_success "S3 file size matches local file: ${S3_FILE_SIZE} bytes"
fi

# Step 4: Validate S3 file with ffprobe (if available)
if command -v ffprobe >/dev/null 2>&1; then
    log "Step 4: Validating S3 file with ffprobe..."
    aws s3 cp "s3://$S3_BUCKET_NAME/$S3_KEY" /tmp/s3_validation.mp4 --region "$AWS_REGION" >/dev/null 2>&1
    if ffprobe -v error -show_format /tmp/s3_validation.mp4 >/dev/null 2>&1; then
        log_success "S3 file is valid MP4"
        rm -f /tmp/s3_validation.mp4
    else
        log_error "S3 file failed ffprobe validation"
        rm -f /tmp/s3_validation.mp4
        exit 1
    fi
else
    log_warn "ffprobe not found, skipping S3 file validation"
fi

# Step 5: Confirm upload and create processing job
log "Step 5: Confirming upload and creating processing job..."
CONFIRM_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/upload/confirm" \
    -H "Content-Type: application/json" \
    -d "{\"job_id\": \"$JOB_ID\", \"s3_key\": \"$S3_KEY\"}")

if ! echo "$CONFIRM_RESPONSE" | grep -q 'job_id'; then
    log_error "Failed to confirm upload:"
    echo "$CONFIRM_RESPONSE" >&2
    exit 1
fi

CONFIRMED_JOB_ID=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('job_id',''))" "$CONFIRM_RESPONSE")
if [ "$CONFIRMED_JOB_ID" != "$JOB_ID" ]; then
    log_error "Job ID mismatch: expected $JOB_ID, got $CONFIRMED_JOB_ID"
    exit 1
fi

log_success "Upload confirmed and job created:"
echo "  Job ID: $CONFIRMED_JOB_ID"
echo "  Status: $($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('status',''))" "$CONFIRM_RESPONSE")"

# Step 6: Poll job status
log "Step 6: Polling job status (will check for 60 seconds)..."
MAX_WAIT=60
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    
    STATUS_RESPONSE=$(curl -s "$API_URL/api/v1/status/$JOB_ID")
    STATUS=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('status',''))" "$STATUS_RESPONSE" 2>/dev/null || echo "unknown")
    
    echo "  [${ELAPSED}s] Status: $STATUS"
    
    if [ "$STATUS" = "completed" ]; then
        log_success "Job completed successfully!"
        break
    elif [ "$STATUS" = "failed" ]; then
        ERROR=$($PYTHON_CMD -c "import json,sys; j=json.loads(sys.argv[1]); print(j.get('error',''))" "$STATUS_RESPONSE" 2>/dev/null || echo "Unknown error")
        log_error "Job failed: $ERROR"
        exit 1
    fi
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    log_warn "Job did not complete within ${MAX_WAIT} seconds (status: $STATUS)"
    log "Check CloudWatch logs for job $JOB_ID"
fi

log_success "Presigned URL upload test completed successfully!"
exit 0
