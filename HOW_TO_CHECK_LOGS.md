# How to Check Website Logs

This guide shows you how to check logs for all components of the LifeStream application.

## 1. Frontend Logs (Next.js - Local)

The frontend runs locally on `http://localhost:3000`. Logs appear in the terminal where you started the dev server.

### Check Frontend Logs

**Option A: Terminal where Next.js is running**
- If you started the frontend with `npm run dev`, logs appear in that terminal
- Look for:
  - Page requests: `GET /upload 200`
  - API calls: `POST /api/...`
  - Errors: Red error messages

**Option B: Browser Console**
1. Open http://localhost:3000 in your browser
2. Press `F12` or `Cmd+Option+I` (Mac) to open Developer Tools
3. Click the **Console** tab
4. You'll see:
   - JavaScript errors
   - API call logs
   - React warnings/errors

**Option C: Check if frontend is running**
```bash
# Check if Next.js process is running
ps aux | grep "next dev" | grep -v grep

# Check port 3000
lsof -i :3000
```

## 2. Backend API Logs (AWS Lambda - CloudWatch)

The API runs on AWS Lambda. Logs are in CloudWatch.

### Quick Check (Last 10 minutes)
```bash
# View recent API logs
aws logs tail /aws/lambda/lifestream-api-staging \
  --since 10m \
  --format short \
  --region us-east-1
```

### Follow Logs in Real-Time
```bash
# Watch API logs as they come in
aws logs tail /aws/lambda/lifestream-api-staging \
  --follow \
  --format short \
  --region us-east-1
```

### Filter for Specific Events
```bash
# Only errors
aws logs tail /aws/lambda/lifestream-api-staging \
  --since 30m \
  --format short \
  --region us-east-1 \
  --filter-pattern "ERROR"

# Only upload-related
aws logs tail /aws/lambda/lifestream-api-staging \
  --since 30m \
  --format short \
  --region us-east-1 \
  --filter-pattern "upload"
```

### Using the Monitor Script
```bash
# Monitor API logs only
./scripts/monitor_logs.sh api 10

# Monitor both API and Processor
./scripts/monitor_logs.sh both 10
```

## 3. Processor Logs (AWS Lambda - CloudWatch)

The video processor runs on AWS Lambda. Logs show the processing pipeline.

### Quick Check (Last 10 minutes)
```bash
# View recent processor logs
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 10m \
  --format short \
  --region us-east-1
```

### Follow Logs in Real-Time
```bash
# Watch processor logs as they come in
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --follow \
  --format short \
  --region us-east-1
```

### Filter for Specific Phases
```bash
# Check for diarization
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 30m \
  --format short \
  --region us-east-1 \
  | grep -i "diarization"

# Check for scene detection
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 30m \
  --format short \
  --region us-east-1 \
  | grep -i "scene"

# Check for summarization
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 30m \
  --format short \
  --region us-east-1 \
  | grep -i "summarization\|Phase 6"
```

### Check for Errors
```bash
# All errors in last hour
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 1h \
  --format short \
  --region us-east-1 \
  | grep -i "error\|exception\|failed"
```

### Using the Monitor Script
```bash
# Monitor processor logs only
./scripts/monitor_logs.sh processor 10
```

## 4. Check Logs for a Specific Job

If you have a job ID from an upload:

```bash
# Replace JOB_ID with your actual job ID
JOB_ID="your-job-id-here"

# Find logs for this job
aws logs filter-log-events \
  --log-group-name /aws/lambda/lifestream-video-processor-staging \
  --filter-pattern "$JOB_ID" \
  --region us-east-1 \
  --query 'events[*].message' \
  --output text
```

## 5. Common Log Patterns to Look For

### Successful Processing
```
✅ Phase 3: Audio processing (diarization + ASR) - MANDATORY...
✅ Diarization complete: X segments, Y unique speakers
✅ ASR complete: X segments with transcripts
✅ Phase 4: Video processing (scene detection) - MANDATORY...
✅ Scene detection complete: X scene boundaries detected
✅ Phase 5: Temporal context synchronization (scene-based chunking)...
✅ Synchronization complete: X scene-based contexts
✅ Phase 6: LLM summarization (MANDATORY)...
✅ Summarization complete: X scene-based time blocks
```

### Errors to Watch For
```
❌ Diarization is mandatory but dependencies are not available
❌ Scene detection failed
❌ LLM summarization failed (mandatory feature)
❌ Context has no audio or video data
```

## 6. Quick Commands Reference

```bash
# Frontend (check if running)
ps aux | grep "next dev"

# API logs (last 10 min)
aws logs tail /aws/lambda/lifestream-api-staging --since 10m --format short --region us-east-1

# Processor logs (last 10 min)
aws logs tail /aws/lambda/lifestream-video-processor-staging --since 10m --format short --region us-east-1

# Monitor both (using script)
./scripts/monitor_logs.sh both 10

# Check for errors only
aws logs tail /aws/lambda/lifestream-video-processor-staging --since 1h --format short --region us-east-1 | grep -i "error"

# Check specific job
aws logs filter-log-events --log-group-name /aws/lambda/lifestream-video-processor-staging --filter-pattern "JOB_ID" --region us-east-1
```

## 7. Browser Developer Tools

For frontend debugging:

1. **Open Developer Tools**: `F12` or `Cmd+Option+I` (Mac)
2. **Console Tab**: JavaScript errors, API responses
3. **Network Tab**: See all API calls, request/response details
4. **Application Tab**: Check localStorage, cookies, etc.

### Network Tab Tips
- Filter by "XHR" or "Fetch" to see API calls
- Click on a request to see:
  - Request headers
  - Request body
  - Response status
  - Response body

## 8. Troubleshooting

### No logs appearing?
```bash
# Check if Lambda functions exist
aws lambda list-functions --region us-east-1 | grep lifestream

# Check log groups exist
aws logs describe-log-groups --region us-east-1 | grep lifestream

# Check AWS credentials
aws sts get-caller-identity
```

### Logs too verbose?
```bash
# Filter for specific keywords
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 30m \
  --format short \
  --region us-east-1 \
  | grep -E "(Phase|Diarization|Scene|Summarization|ERROR)"
```

### Need more context?
```bash
# Get full log stream
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 1h \
  --format detailed \
  --region us-east-1
```

---

**Quick Start:** Use `./scripts/monitor_logs.sh both 10` to monitor both API and Processor logs in real-time!
