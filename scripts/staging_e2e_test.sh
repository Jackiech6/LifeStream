#!/bin/bash
# End-to-end staging test for LifeStream backend
# - Generates a small deterministic test video if missing
# - Uploads via API
# - Polls job status
# - Fetches summary and runs a query

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VIDEO_DIR="$PROJECT_ROOT/test_assets"
VIDEO_PATH="$VIDEO_DIR/test_5s.mp4"
AWS_REGION="${AWS_REGION:-us-east-1}"

API_URL="$(cd "$PROJECT_ROOT/infrastructure" && terraform output -raw api_gateway_url)"

log() { echo "[staging-e2e] $*"; }

# 0) Ensure test video exists and is valid
mkdir -p "$VIDEO_DIR"
if [ ! -f "$VIDEO_PATH" ]; then
  log "Test video not found, generating at $VIDEO_PATH"
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg not found. Install it on macOS with: brew install ffmpeg" >&2
    exit 1
  fi
  ffmpeg -y \
    -f lavfi -i testsrc=duration=5:size=640x360:rate=25 \
    -f lavfi -i sine=frequency=1000:duration=5 \
    -c:v libx264 -c:a aac \
    -movflags +faststart \
    "$VIDEO_PATH"
  log "Generated test video: $VIDEO_PATH"
else
  log "Using existing test video: $VIDEO_PATH"
fi

# Verify the video file is valid before uploading
if command -v ffprobe >/dev/null 2>&1; then
  if ! ffprobe -v error -show_format "$VIDEO_PATH" >/dev/null 2>&1; then
    echo "Error: Test video file appears corrupted. Regenerating..." >&2
    rm -f "$VIDEO_PATH"
    ffmpeg -y \
      -f lavfi -i testsrc=duration=5:size=640x360:rate=25 \
      -f lavfi -i sine=frequency=1000:duration=5 \
      -c:v libx264 -c:a aac \
      -movflags +faststart \
      "$VIDEO_PATH"
  fi
  VIDEO_SIZE=$(stat -f%z "$VIDEO_PATH" 2>/dev/null || stat -c%s "$VIDEO_PATH" 2>/dev/null || echo "0")
  log "Test video validated: $VIDEO_SIZE bytes"
fi

# Extract job_id using python3 (or python) with JSON passed as an argument
# Try python3 first, fall back to python
PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
else
  echo "Error: Neither python3 nor python found in PATH" >&2
  exit 1
fi

# 1) Get presigned URL
log "Step 1: Requesting presigned URL..."
VIDEO_SIZE=$(stat -f%z "$VIDEO_PATH" 2>/dev/null || stat -c%s "$VIDEO_PATH" 2>/dev/null || echo "0")
PRESIGNED_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/upload/presigned-url" \
  -H "Content-Type: application/json" \
  -d "{\"filename\": \"$(basename "$VIDEO_PATH")\", \"file_size\": $VIDEO_SIZE}")

if ! echo "$PRESIGNED_RESPONSE" | grep -q 'upload_url'; then
  echo "Failed to get presigned URL:" >&2
  echo "$PRESIGNED_RESPONSE" >&2
  exit 1
fi

UPLOAD_URL=$($PYTHON_CMD -c 'import json,sys; j=json.loads(sys.argv[1]); print(j.get("upload_url",""))' "$PRESIGNED_RESPONSE")
S3_KEY=$($PYTHON_CMD -c 'import json,sys; j=json.loads(sys.argv[1]); print(j.get("s3_key",""))' "$PRESIGNED_RESPONSE")
JOB_ID=$($PYTHON_CMD -c 'import json,sys; j=json.loads(sys.argv[1]); print(j.get("job_id",""))' "$PRESIGNED_RESPONSE")

if [ -z "$UPLOAD_URL" ] || [ -z "$S3_KEY" ] || [ -z "$JOB_ID" ]; then
  echo "Failed to extract presigned URL data:" >&2
  echo "$PRESIGNED_RESPONSE" >&2
  exit 1
fi

log "Presigned URL generated; job_id=$JOB_ID"

# 2) Upload file directly to S3
log "Step 2: Uploading file to S3..."
UPLOAD_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X PUT \
  --data-binary "@$VIDEO_PATH" \
  -H "Content-Type: video/mp4" \
  "$UPLOAD_URL")

if [ "$UPLOAD_HTTP_CODE" != "200" ]; then
  echo "S3 upload failed with HTTP code: $UPLOAD_HTTP_CODE" >&2
  exit 1
fi

log "File uploaded to S3 successfully"

# 3) Confirm upload
log "Step 3: Confirming upload..."
CONFIRM_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/upload/confirm" \
  -H "Content-Type: application/json" \
  -d "{\"job_id\": \"$JOB_ID\", \"s3_key\": \"$S3_KEY\"}")

if ! echo "$CONFIRM_RESPONSE" | grep -q 'job_id'; then
  echo "Failed to confirm upload:" >&2
  echo "$CONFIRM_RESPONSE" >&2
  exit 1
fi

log "Upload confirmed; job_id=$JOB_ID"

# 4) Poll job status
MAX_ATTEMPTS=40
SLEEP_SECONDS=15
attempt=1
STATUS="unknown"

while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
  log "Polling status (attempt $attempt/$MAX_ATTEMPTS)..."
  STATUS_JSON=$(curl -s "$API_URL/api/v1/status/$JOB_ID" || true)
  # Extract status using python3 (or python) with JSON passed as an argument
  STATUS=$($PYTHON_CMD -c 'import json,sys; j=json.loads(sys.argv[1]); print(j.get("status",""))' "$STATUS_JSON")

  log "Current status: $STATUS"

  if [ "$STATUS" = "completed" ]; then
    break
  fi

  if [ "$STATUS" = "failed" ]; then
    echo "Job failed. Full status response:" >&2
    echo "$STATUS_JSON" >&2
    exit 1
  fi

  attempt=$((attempt + 1))
  sleep "$SLEEP_SECONDS"
done

if [ "$STATUS" != "completed" ]; then
  echo "Job did not complete within timeout (status=$STATUS)" >&2
  exit 1
fi

# 3) Fetch summary
log "Fetching summary for job $JOB_ID..."
SUMMARY_JSON=$(curl -s "$API_URL/api/v1/summary/$JOB_ID" || true)

if ! echo "$SUMMARY_JSON" | grep -q 'summary'; then
  echo "Summary response does not contain 'summary':" >&2
  echo "$SUMMARY_JSON" >&2
  exit 1
fi

# 4) Run a simple query
log "Running semantic query..."
QUERY_JSON=$(curl -s -X POST "$API_URL/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"What happens in the test video?","top_k":3}')

if ! echo "$QUERY_JSON" | grep -q 'results'; then
  echo "Query response does not contain 'results':" >&2
  echo "$QUERY_JSON" >&2
  exit 1
fi

log "E2E staging test PASSED"
exit 0
