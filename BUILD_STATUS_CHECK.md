# How to Check Build Status

## Quick Status Check Commands

### 1. Check if build process is running
```bash
ps aux | grep -E "(build_and_push_processor|docker build)" | grep -v grep
```
- **If output exists:** Build is still running
- **If no output:** Build process has finished (success or failure)

### 2. Check latest build log
```bash
# Find the latest log file
ls -lt /tmp/processor*.log | head -1

# Check if build completed
tail -20 /tmp/processor_final_deps.log | grep -E "(pushed successfully|Image URI|Next steps)"
```
- **If you see "✅ Image pushed successfully":** Build completed ✅
- **If you see "pushing layers" or ends abruptly:** Build may still be in progress or failed

### 3. Check ECR for latest image
```bash
aws ecr describe-images \
  --repository-name lifestream-lambda-processor-staging \
  --region us-east-1 \
  --image-ids imageTag=latest \
  --query 'imageDetails[0].[imagePushedAt,imageDigest]' \
  --output text
```
- Shows when the latest image was pushed to ECR

### 4. Check Lambda function status
```bash
aws lambda get-function \
  --function-name lifestream-video-processor-staging \
  --region us-east-1 \
  --query '[Configuration.ImageUri, Configuration.LastModified, Configuration.LastUpdateStatus]' \
  --output text
```
- Shows if Lambda has been updated with the new image

### 5. Check for build errors
```bash
# Check for errors in the build log
grep -i "error\|failed\|⚠️" /tmp/processor_final_deps.log | tail -10

# Check dependency installation status
grep -E "(✅|⚠️|installed|OK)" /tmp/processor_final_deps.log | grep -E "(scenedetect|scipy|opencv|pytorch_lightning)" | tail -10
```

## Current Build Status (as of last check)

Based on the latest log file (`/tmp/processor_final_deps.log`):

### ✅ Completed Steps:
- OpenCV installed successfully
- PyTorch installed
- pytorch_lightning installed
- Most dependencies installed

### ❌ Issues Found:
- **scipy:** Not properly installed (pyannote-core requires it)
- **scenedetect:** Not available (⚠️ scenedetect not available)
- **Build status:** Log ends at "pushing layers" stage - may be incomplete

### Next Steps:
1. If build is still running, wait for it to complete
2. If build failed, check the error messages and fix the Dockerfile
3. The scipy installation issue needs to be fixed - it should be installed BEFORE pyannote.audio

## Expected Build Time
- **Normal build:** 15-25 minutes
- **With scipy from source:** 30-45 minutes
- **Image push to ECR:** 3-10 minutes (depends on image size and network)

## Quick Status Script

Save this as `check_build_status.sh`:

```bash
#!/bin/bash
echo "=== Build Status Check ==="
echo ""

# Check if running
if ps aux | grep -E "(build_and_push_processor|docker build)" | grep -v grep > /dev/null; then
    echo "🔄 Build is RUNNING"
else
    echo "⏸️  Build process is NOT running"
fi

# Check log
LATEST_LOG=$(ls -t /tmp/processor*.log 2>/dev/null | head -1)
if [ -f "$LATEST_LOG" ]; then
    echo ""
    echo "📄 Latest log: $LATEST_LOG"
    if grep -q "pushed successfully\|Image URI" "$LATEST_LOG" 2>/dev/null; then
        echo "✅ Build COMPLETED successfully"
    else
        echo "❌ Build NOT completed or still in progress"
        echo "Last 3 lines:"
        tail -3 "$LATEST_LOG"
    fi
fi

# Check ECR
echo ""
echo "📦 Latest ECR image:"
aws ecr describe-images \
  --repository-name lifestream-lambda-processor-staging \
  --region us-east-1 \
  --image-ids imageTag=latest \
  --query 'imageDetails[0].imagePushedAt' \
  --output text 2>/dev/null || echo "Could not check ECR"
```
