#!/bin/bash
# Quick test script for video upload with CloudWatch monitoring
# This script uploads a test video and monitors CloudWatch logs in real-time

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VIDEO_PATH="$PROJECT_ROOT/test_assets/test_5s.mp4"
AWS_REGION="${AWS_REGION:-us-east-1}"

API_URL="$(cd "$PROJECT_ROOT/infrastructure" && terraform output -raw api_gateway_url)"

log() { echo "[test-upload] $*"; }

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if test video exists
if [ ! -f "$VIDEO_PATH" ]; then
    log "Test video not found. Generating..."
    mkdir -p "$(dirname "$VIDEO_PATH")"
    if ! command -v ffmpeg >/dev/null 2>&1; then
        echo "ffmpeg not found. Install with: brew install ffmpeg" >&2
        exit 1
    fi
    ffmpeg -y \
        -f lavfi -i testsrc=duration=5:size=640x360:rate=25 \
        -f lavfi -i sine=frequency=1000:duration=5 \
        -c:v libx264 -c:a aac \
        -movflags +faststart \
        "$VIDEO_PATH"
fi

VIDEO_SIZE=$(stat -f%z "$VIDEO_PATH" 2>/dev/null || stat -c%s "$VIDEO_PATH" 2>/dev/null || echo "0")
log "Test video: $VIDEO_PATH (${VIDEO_SIZE} bytes)"

# Start CloudWatch log monitoring in background
log "Starting CloudWatch log monitoring..."
API_LOG_PID=""
PROCESSOR_LOG_PID=""

cleanup() {
    log "Stopping log monitoring..."
    [ -n "$API_LOG_PID" ] && kill "$API_LOG_PID" 2>/dev/null || true
    [ -n "$PROCESSOR_LOG_PID" ] && kill "$PROCESSOR_LOG_PID" 2>/dev/null || true
    exit 0
}

trap cleanup INT TERM

# Monitor API Lambda logs
(
    aws logs tail /aws/lambda/lifestream-api-staging \
        --since 1m \
        --format short \
        --region "$AWS_REGION" \
        --follow 2>&1 | while IFS= read -r line; do
            if echo "$line" | grep -qE "(ERROR|Exception|Traceback|upload|Read|bytes|size)"; then
                echo -e "${YELLOW}[API]${NC} $line"
            fi
        done
) &
API_LOG_PID=$!

# Monitor Processor Lambda logs
(
    aws logs tail /aws/lambda/lifestream-video-processor-staging \
        --since 1m \
        --format short \
        --region "$AWS_REGION" \
        --follow 2>&1 | while IFS= read -r line; do
            if echo "$line" | grep -qE "(ERROR|Exception|Traceback|Processing|moov|FFprobe)"; then
                echo -e "${RED}[PROCESSOR]${NC} $line"
            fi
        done
) &
PROCESSOR_LOG_PID=$!

sleep 2

# Upload the video
log "Uploading video to $API_URL/api/v1/upload..."
UPLOAD_START=$(date +%s)

UPLOAD_JSON=$(curl -s --max-time 300 --show-error -X POST "$API_URL/api/v1/upload" \
    -F "file=@$VIDEO_PATH;type=video/mp4" || true)

UPLOAD_END=$(date +%s)
UPLOAD_DURATION=$((UPLOAD_END - UPLOAD_START))

if ! echo "$UPLOAD_JSON" | grep -q 'job_id'; then
    echo -e "${RED}Upload failed!${NC}" >&2
    echo "$UPLOAD_JSON" >&2
    cleanup
    exit 1
fi

# Extract job_id
PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "Error: Neither python3 nor python found" >&2
    cleanup
    exit 1
fi

JOB_ID=$($PYTHON_CMD -c 'import json,sys; j=json.loads(sys.argv[1]); print(j.get("job_id",""))' "$UPLOAD_JSON")
S3_KEY=$($PYTHON_CMD -c 'import json,sys; j=json.loads(sys.argv[1]); print(j.get("video_url","").split("/")[-1] if "/" in j.get("video_url","") else "")' "$UPLOAD_JSON")

if [ -z "$JOB_ID" ]; then
    echo -e "${RED}Failed to extract job_id${NC}" >&2
    echo "$UPLOAD_JSON" >&2
    cleanup
    exit 1
fi

echo -e "${GREEN}Upload successful!${NC}"
echo "  Job ID: $JOB_ID"
echo "  Upload duration: ${UPLOAD_DURATION}s"
echo "  S3 Key: $S3_KEY"

# Wait a moment for S3 upload to complete
sleep 3

# Check S3 file size
if [ -n "$S3_KEY" ]; then
    BUCKET_NAME="lifestream-videos-staging-533267430850"
    S3_SIZE=$(aws s3 ls "s3://$BUCKET_NAME/$S3_KEY" --region "$AWS_REGION" --human-readable 2>/dev/null | awk '{print $3}' || echo "not found")
    echo "  S3 file size: $S3_SIZE"
    
    if [ "$S3_SIZE" != "not found" ]; then
        # Download and verify
        TEMP_DOWNLOAD="/tmp/test_download_$(date +%s).mp4"
        aws s3 cp "s3://$BUCKET_NAME/$S3_KEY" "$TEMP_DOWNLOAD" --region "$AWS_REGION" >/dev/null 2>&1
        if [ -f "$TEMP_DOWNLOAD" ]; then
            DOWNLOAD_SIZE=$(stat -f%z "$TEMP_DOWNLOAD" 2>/dev/null || stat -c%s "$TEMP_DOWNLOAD" 2>/dev/null || echo "0")
            echo "  Downloaded size: ${DOWNLOAD_SIZE} bytes"
            
            # Try to validate with ffprobe
            if command -v ffprobe >/dev/null 2>&1; then
                if ffprobe -v error -show_format "$TEMP_DOWNLOAD" >/dev/null 2>&1; then
                    echo -e "  ${GREEN}✓ File is valid MP4${NC}"
                else
                    echo -e "  ${RED}✗ File is corrupted (moov atom missing)${NC}"
                fi
            fi
            rm -f "$TEMP_DOWNLOAD"
        fi
    fi
fi

echo ""
echo "Monitoring logs for 60 seconds (Ctrl+C to stop)..."
echo ""

# Keep monitoring for 60 seconds
sleep 60

cleanup
