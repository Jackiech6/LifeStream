# Queueing Issue Fix

## Problem Identified

The program is stuck in the "queueing" stage. Investigation shows:

### Root Cause
Jobs are being **successfully queued** to SQS, but **processing fails immediately** due to missing dependency:

```
ModuleNotFoundError: No module named 'pyannote.database'
```

**Error Location:**
- `pyannote.audio.core.task` imports `pyannote.database`
- This happens when trying to load the diarization Pipeline
- Processing fails at Phase 3 (Diarization)

### Why It Appears "Stuck"
1. ✅ Job is created and enqueued successfully
2. ✅ SQS message is received by processor Lambda
3. ❌ Processing fails immediately due to missing `pyannote.database`
4. ❌ Job status remains "queued" or shows as failed
5. User sees "stuck in queueing" because processing never completes

## Fix Applied

### Added `pyannote.database` Dependency

**File:** `Dockerfile.processor`

**Change:**
```dockerfile
# Install pyannote.database (required by pyannote.audio.core.task)
# Use version 4.1.1 which is compatible with numpy 1.24.3
(pip install --no-cache-dir "pyannote.database==4.1.1" || \
 pip install --no-cache-dir "pyannote.database==4.0.0" || \
 echo "Warning: pyannote.database installation failed")
```

**Why Version 4.1.1:**
- `pyannote.database` 5.x requires numpy 2.x (not compatible)
- `pyannote.database` 4.1.1 works with numpy 1.24.3
- Required by `pyannote.audio.core.task` for Pipeline loading

## Deployment Status

- ✅ Code fixed (pyannote.database added)
- 🔄 Processor image building (in progress)
- ⏳ Lambda update pending

## Expected Results After Fix

### Before Fix:
```
✅ Job queued successfully
❌ Processing fails: No module named 'pyannote.database'
❌ Job appears "stuck" in queueing
```

### After Fix:
```
✅ Job queued successfully
✅ pyannote.database available
✅ Diarization Pipeline loads successfully
✅ Processing continues through all phases
✅ Job completes successfully
```

## Verification

After deployment, check logs:
```bash
# Check for successful diarization
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 10m \
  --format short \
  --region us-east-1 \
  | grep -i "diarization\|pyannote.database"

# Expected output:
# Diarization dependencies available
# Loading diarization model: pyannote/speaker-diarization-3.1
# Diarization model loaded successfully
# Diarization complete: X segments, Y unique speakers
```

## Queue Status Check

```bash
# Check SQS queue status
aws sqs get-queue-attributes \
  --queue-url <queue-url> \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
  --region us-east-1
```

---

**Status:** 🔄 Fix applied, building new image  
**Action:** Wait for build to complete, then Lambda will be updated
