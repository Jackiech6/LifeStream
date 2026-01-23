#!/bin/bash
# Monitor CloudWatch logs for API and Processor Lambdas
# Usage: ./scripts/monitor_logs.sh [api|processor|both] [since_minutes]

set -euo pipefail

LOG_TYPE="${1:-both}"
SINCE_MINUTES="${2:-10}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

monitor_api() {
    echo -e "${BLUE}=== API Lambda Logs ===${NC}"
    aws logs tail /aws/lambda/lifestream-api-staging \
        --since "${SINCE_MINUTES}m" \
        --format short \
        --region "$AWS_REGION" \
        --follow 2>&1 | while IFS= read -r line; do
            if echo "$line" | grep -qE "ERROR"; then
                echo -e "${RED}[API ERROR]${NC} $line"
            elif echo "$line" | grep -qE "(upload|Read|bytes|size|File verified)"; then
                echo -e "${GREEN}[API]${NC} $line"
            elif echo "$line" | grep -qE "(WARNING|Exception)"; then
                echo -e "${YELLOW}[API WARN]${NC} $line"
            else
                echo "[API] $line"
            fi
        done
}

monitor_processor() {
    echo -e "${BLUE}=== Processor Lambda Logs ===${NC}"
    aws logs tail /aws/lambda/lifestream-video-processor-staging \
        --since "${SINCE_MINUTES}m" \
        --format short \
        --region "$AWS_REGION" \
        --follow 2>&1 | while IFS= read -r line; do
            if echo "$line" | grep -qE "ERROR"; then
                echo -e "${RED}[PROC ERROR]${NC} $line"
            elif echo "$line" | grep -qE "(moov|FFprobe|corrupt)"; then
                echo -e "${RED}[PROC CORRUPT]${NC} $line"
            elif echo "$line" | grep -qE "(Processing|Downloading|Phase)"; then
                echo -e "${GREEN}[PROC]${NC} $line"
            elif echo "$line" | grep -qE "(WARNING|Exception)"; then
                echo -e "${YELLOW}[PROC WARN]${NC} $line"
            else
                echo "[PROC] $line"
            fi
        done
}

case "$LOG_TYPE" in
    api)
        monitor_api
        ;;
    processor)
        monitor_processor
        ;;
    both)
        # Run both in parallel using background processes
        monitor_api &
        API_PID=$!
        monitor_processor &
        PROC_PID=$!
        
        trap "kill $API_PID $PROC_PID 2>/dev/null; exit" INT TERM
        wait
        ;;
    *)
        echo "Usage: $0 [api|processor|both] [since_minutes]"
        exit 1
        ;;
esac
