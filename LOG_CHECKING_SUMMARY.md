# Quick Guide: How to Check Website Logs

## 1. Frontend Logs (Next.js - Local)

**Where:** Terminal where you ran `npm run dev` in the `frontend/` directory

**Or Browser Console:**
1. Open http://localhost:3000
2. Press `F12` (or `Cmd+Option+I` on Mac)
3. Click **Console** tab for JavaScript errors
4. Click **Network** tab for API calls

## 2. Backend API Logs (AWS CloudWatch)

**Quick Check (Last 10 minutes):**
```bash
aws logs tail /aws/lambda/lifestream-api-staging \
  --since 10m \
  --format short \
  --region us-east-1
```

**Follow in Real-Time:**
```bash
aws logs tail /aws/lambda/lifestream-api-staging \
  --follow \
  --format short \
  --region us-east-1
```

## 3. Processor Logs (AWS CloudWatch)

**Quick Check (Last 10 minutes):**
```bash
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 10m \
  --format short \
  --region us-east-1
```

**Follow in Real-Time:**
```bash
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --follow \
  --format short \
  --region us-east-1
```

**Check for Errors:**
```bash
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 1h \
  --format short \
  --region us-east-1 \
  | grep -i "error\|exception\|failed"
```

**Check Specific Phases:**
```bash
# Diarization
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 30m --format short --region us-east-1 \
  | grep -i "diarization"

# Scene detection
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 30m --format short --region us-east-1 \
  | grep -i "scene"

# Summarization
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 30m --format short --region us-east-1 \
  | grep -i "summarization\|Phase 6"
```

## 4. Easy Way - Use Monitor Script

**Monitor Both API and Processor:**
```bash
./scripts/monitor_logs.sh both 10
```

**Monitor API Only:**
```bash
./scripts/monitor_logs.sh api 10
```

**Monitor Processor Only:**
```bash
./scripts/monitor_logs.sh processor 10
```

## 5. Check Logs for Specific Job

If you have a job ID:
```bash
JOB_ID="your-job-id-here"
aws logs filter-log-events \
  --log-group-name /aws/lambda/lifestream-video-processor-staging \
  --filter-pattern "$JOB_ID" \
  --region us-east-1 \
  --query 'events[*].message' \
  --output text
```

## Common Log Patterns

### ✅ Successful Processing
- `Diarization complete: X segments, Y unique speakers`
- `Scene detection complete: X scene boundaries detected`
- `Synchronization complete: X scene-based contexts`
- `Summarization complete: X scene-based time blocks`

### ❌ Errors to Watch For
- `Diarization is mandatory but dependencies are not available`
- `Scene detection failed`
- `LLM summarization failed (mandatory feature)`
- `No module named 'lazy_loader'` (missing dependency)

---

**Quick Start:** `./scripts/monitor_logs.sh both 10`

**Full Guide:** See `HOW_TO_CHECK_LOGS.md` for detailed instructions
