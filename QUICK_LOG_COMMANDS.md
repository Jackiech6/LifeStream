# Quick Log Commands

## Frontend Logs (Next.js)

**Check if running:**
```bash
ps aux | grep "next dev" | grep -v grep
```

**View in terminal:**
- Logs appear in the terminal where you ran `npm run dev` in the `frontend/` directory
- Or check browser console: Press `F12` → Console tab

## Backend API Logs (CloudWatch)

**Last 10 minutes:**
```bash
aws logs tail /aws/lambda/lifestream-api-staging \
  --since 10m \
  --format short \
  --region us-east-1
```

**Follow in real-time:**
```bash
aws logs tail /aws/lambda/lifestream-api-staging \
  --follow \
  --format short \
  --region us-east-1
```

## Processor Logs (CloudWatch)

**Last 10 minutes:**
```bash
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 10m \
  --format short \
  --region us-east-1
```

**Follow in real-time:**
```bash
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --follow \
  --format short \
  --region us-east-1
```

**Check for errors:**
```bash
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 1h \
  --format short \
  --region us-east-1 \
  | grep -i "error\|exception\|failed"
```

**Check specific phases:**
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

## Monitor Both (Easy Way)

**Use the monitor script:**
```bash
# Monitor both API and Processor
./scripts/monitor_logs.sh both 10

# Monitor API only
./scripts/monitor_logs.sh api 10

# Monitor Processor only
./scripts/monitor_logs.sh processor 10
```

## Browser Developer Tools

1. Open http://localhost:3000
2. Press `F12` (or `Cmd+Option+I` on Mac)
3. **Console tab**: JavaScript errors, API responses
4. **Network tab**: All API calls, request/response details

---

**Quick Start:** `./scripts/monitor_logs.sh both 10`
