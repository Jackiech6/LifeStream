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

# 0) Ensure test video exists
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
    "$VIDEO_PATH"
else
  log "Using existing test video: $VIDEO_PATH"
fi

# 1) Upload via API
log "Uploading test video via API..."
UPLOAD_JSON=$(curl -s -X POST "$API_URL/api/v1/upload" \
  -F "file=@$VIDEO_PATH" || true)

if ! echo "$UPLOAD_JSON" | grep -q 'job_id'; then
  echo "Upload failed or unexpected response:" >&2
  echo "$UPLOAD_JSON" >&2
  exit 1
fi

# Extract job_id using python3 with JSON passed as an argument (more robust than stdin heredoc)
JOB_ID=$(python3 -c 'import json,sys; j=json.loads(sys.argv[1]); print(j.get("job_id",""))' "$UPLOAD_JSON")

if [ -z "$JOB_ID" ]; then
  echo "Failed to extract job_id from upload response:" >&2
  echo "$UPLOAD_JSON" >&2
  exit 1
fi

log "Upload accepted; job_id=$JOB_ID"

# 2) Poll job status
MAX_ATTEMPTS=40
SLEEP_SECONDS=15
attempt=1
STATUS="unknown"

while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
  log "Polling status (attempt $attempt/$MAX_ATTEMPTS)..."
  STATUS_JSON=$(curl -s "$API_URL/api/v1/status/$JOB_ID" || true)
  # Extract status using python3 with JSON passed as an argument
  STATUS=$(python3 -c 'import json,sys; j=json.loads(sys.argv[1]); print(j.get("status",""))' "$STATUS_JSON")

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
