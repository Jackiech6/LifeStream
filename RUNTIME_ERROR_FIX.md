# Runtime Error Fix - Diarization Dependencies

## Problem Identified

The logs showed this error:
```
RuntimeError: Diarization is mandatory but dependencies are not available. 
Install required dependencies: pip install pyannote.audio torch pytorch-lightning huggingface-hub
```

**Root Cause:** Missing `lazy_loader` dependency required by `pyannote.audio`

**Error Details:**
```
No module named 'lazy_loader'
```

## Fix Applied

### 1. Added Missing Dependency

**File:** `Dockerfile.processor`

**Change:**
```dockerfile
# Before
RUN pip install --no-cache-dir \
    "einops>=0.6.0" \
    "huggingface-hub>=0.20.0" \
    "pytorch-lightning>=2.0.0,<3.0.0" \
    ...

# After
RUN pip install --no-cache-dir \
    "einops>=0.6.0" \
    "huggingface-hub>=0.20.0" \
    "pytorch-lightning>=2.0.0,<3.0.0" \
    "lazy_loader>=0.3" \  # ← Added
    ...
```

### 2. Made Diarization Initialization Mandatory

**File:** `src/audio/diarization.py`

**Changes:**
- `_check_dependencies()` now raises `ImportError` instead of setting a flag
- `_load_model()` now raises `RuntimeError` instead of setting pipeline to None
- Removed all graceful degradation paths

**Before:**
```python
except ImportError as e:
    logger.warning("Diarization dependencies not available - skipping")
    self._dependencies_available = False
    return
```

**After:**
```python
except ImportError as e:
    raise ImportError(
        f"Diarization is mandatory but dependencies are not available: {e}. "
        "Install required dependencies: pip install pyannote.audio torch pytorch-lightning huggingface-hub lazy_loader"
    ) from e
```

## Deployment Steps

### 1. Build Processor Image
```bash
./scripts/build_and_push_processor_image.sh
```

This will:
- Install `lazy_loader>=0.3` along with other dependencies
- Build Docker image with all mandatory dependencies
- Push to ECR

### 2. Update Lambda Function
```bash
PROC_URI="533267430850.dkr.ecr.us-east-1.amazonaws.com/lifestream-lambda-processor-staging:latest"
aws lambda update-function-code \
  --function-name lifestream-video-processor-staging \
  --image-uri "$PROC_URI" \
  --region us-east-1
```

### 3. Verify Deployment
```bash
# Check Lambda status
aws lambda get-function \
  --function-name lifestream-video-processor-staging \
  --region us-east-1 \
  --query 'Configuration.LastUpdateStatus' \
  --output text

# Should show: Successful
```

## Expected Results After Fix

### Before Fix:
```
❌ RuntimeError: Diarization is mandatory but dependencies are not available
❌ No module named 'lazy_loader'
❌ Processing fails at Phase 3
```

### After Fix:
```
✅ Diarization dependencies available
✅ lazy_loader installed
✅ Diarization model loaded successfully
✅ Processing continues through all phases
```

## Verification

After deployment, check logs:
```bash
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 10m \
  --format short \
  --region us-east-1 \
  | grep -i "diarization\|lazy_loader"
```

**Expected output:**
- `Diarization dependencies available`
- `Loading diarization model: pyannote/speaker-diarization-3.1`
- `Diarization model loaded successfully`
- `Diarization complete: X segments, Y unique speakers`

## Current Status

- ✅ Code fixed (lazy_loader added, mandatory error handling)
- 🔄 Processor image building (in progress)
- ⏳ Lambda update pending (after build completes)

---

**Next Steps:**
1. Wait for build to complete (~15-20 minutes)
2. Lambda will be updated automatically
3. Upload a new video to test
4. Verify diarization works in logs
