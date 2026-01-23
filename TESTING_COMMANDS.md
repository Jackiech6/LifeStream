# Testing and Monitoring Commands

## Quick Test Upload with Real-time Monitoring

Run the automated test script that uploads a video and monitors logs:

```bash
cd /Users/chenjackie/Desktop/LifeStream
./scripts/test_upload_and_monitor.sh
```

This script will:
- Generate test video if needed
- Upload via API
- Monitor both API and Processor Lambda logs in real-time
- Check S3 file size and validate with ffprobe
- Run for 60 seconds (Ctrl+C to stop early)

## Manual Testing

### 1. Upload Test Video

```bash
cd /Users/chenjackie/Desktop/LifeStream

# Get API URL
API_URL=$(cd infrastructure && terraform output -raw api_gateway_url)

# Upload video
curl -v -X POST "$API_URL/api/v1/upload" \
  -F "file=@test_assets/test_5s.mp4;type=video/mp4"

# Extract job_id from response
JOB_ID=$(curl -s -X POST "$API_URL/api/v1/upload" \
  -F "file=@test_assets/test_5s.mp4;type=video/mp4" | \
  python3 -c 'import json,sys; print(json.load(sys.stdin).get("job_id",""))')

echo "Job ID: $JOB_ID"
```

### 2. Monitor CloudWatch Logs

#### Monitor Both Lambdas (Recommended)
```bash
./scripts/monitor_logs.sh both 10
```

#### Monitor API Lambda Only
```bash
./scripts/monitor_logs.sh api 10
```

#### Monitor Processor Lambda Only
```bash
./scripts/monitor_logs.sh processor 10
```

#### Manual Log Commands

**API Lambda logs (last 10 minutes):**
```bash
aws logs tail /aws/lambda/lifestream-api-staging \
  --since 10m \
  --format short \
  --region us-east-1
```

**API Lambda logs (follow mode):**
```bash
aws logs tail /aws/lambda/lifestream-api-staging \
  --since 1m \
  --format short \
  --region us-east-1 \
  --follow
```

**Processor Lambda logs (last 10 minutes):**
```bash
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 10m \
  --format short \
  --region us-east-1
```

**Processor Lambda logs (follow mode):**
```bash
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 1m \
  --format short \
  --region us-east-1 \
  --follow
```

**Filter for specific errors:**
```bash
# API errors
aws logs tail /aws/lambda/lifestream-api-staging \
  --since 10m \
  --format short \
  --region us-east-1 \
  --filter-pattern "ERROR"

# Processor corruption errors
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 10m \
  --format short \
  --region us-east-1 \
  --filter-pattern "moov"
```

### 3. Check S3 File

```bash
# List recent uploads
aws s3 ls s3://lifestream-videos-staging-533267430850/uploads/ \
  --region us-east-1 \
  --human-readable \
  | tail -5

# Download and verify a specific file
S3_KEY="uploads/20260122_173107_tmp5jio484d.mp4"
aws s3 cp "s3://lifestream-videos-staging-533267430850/$S3_KEY" /tmp/test.mp4 --region us-east-1

# Check file size
ls -lh /tmp/test.mp4

# Validate with ffprobe
ffprobe -v error -show_format /tmp/test.mp4

# Check for corruption
ffprobe -v error -show_format /tmp/test.mp4 2>&1 | grep -q "moov" && echo "Valid" || echo "Corrupted"
```

### 4. Check Job Status

```bash
# Get job status
curl -s "$API_URL/api/v1/status/$JOB_ID" | python3 -m json.tool

# Get summary (after completion)
curl -s "$API_URL/api/v1/summary/$JOB_ID" | python3 -m json.tool
```

### 5. Full E2E Test

```bash
./scripts/staging_e2e_test.sh
```

## Debugging File Corruption

### Check File Sizes

```bash
# Local file
ls -lh test_assets/test_5s.mp4

# S3 file (replace with actual key)
S3_KEY="uploads/20260122_173107_tmp5jio484d.mp4"
aws s3 ls "s3://lifestream-videos-staging-533267430850/$S3_KEY" --region us-east-1 --human-readable

# Compare
LOCAL_SIZE=$(stat -f%z test_assets/test_5s.mp4 2>/dev/null || stat -c%s test_assets/test_5s.mp4)
S3_SIZE=$(aws s3api head-object --bucket lifestream-videos-staging-533267430850 --key "$S3_KEY" --region us-east-1 --query 'ContentLength' --output text)
echo "Local: $LOCAL_SIZE bytes"
echo "S3: $S3_SIZE bytes"
echo "Difference: $((S3_SIZE - LOCAL_SIZE)) bytes"
```

### Check File Content

```bash
# Download from S3
aws s3 cp "s3://lifestream-videos-staging-533267430850/$S3_KEY" /tmp/s3_file.mp4 --region us-east-1

# Compare first 100 bytes
echo "Local file:"
head -c 100 test_assets/test_5s.mp4 | od -c | head -5

echo "S3 file:"
head -c 100 /tmp/s3_file.mp4 | od -c | head -5

# Check for UTF-8 replacement characters (indicates encoding corruption)
hexdump -C /tmp/s3_file.mp4 | grep -E "ef bf bd" && echo "Found UTF-8 replacement chars - file is corrupted!"
```

### Check API Lambda Logs for File Read

```bash
# Look for file read logs
aws logs tail /aws/lambda/lifestream-api-staging \
  --since 10m \
  --format short \
  --region us-east-1 \
  | grep -E "(Read|bytes|size|chunk|File verified|Starting file read)"
```

## Common Issues

### File Size Mismatch
- **Symptom**: S3 file is ~2x the size of local file
- **Check**: API Lambda logs for "Read X bytes" messages
- **Fix**: Check if multipart boundaries are being included

### Missing Moov Atom
- **Symptom**: FFprobe error "moov atom not found"
- **Check**: Download file from S3 and validate locally
- **Fix**: File is corrupted during upload - check encoding

### No Logs Appearing
- **Check**: Lambda function is updated
- **Check**: Logs are being written (check CloudWatch directly)
- **Fix**: Wait for Lambda update to complete (~30 seconds)
