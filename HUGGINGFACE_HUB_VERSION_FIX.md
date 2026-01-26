# ✅ HuggingFace Hub Version Compatibility Fix

## Issue Identified

**Error:** `TypeError: hf_hub_download() got an unexpected keyword argument 'use_auth_token'`

**Root Cause:**
- `pyannote.audio` 3.1.1 internally calls `hf_hub_download()` with `use_auth_token` parameter
- `huggingface-hub>=0.20.0` completely removed support for `use_auth_token` (replaced with `token`)
- This creates an incompatibility where `pyannote.audio` 3.1.1's internal code fails

## Fix Applied

**File:** `Dockerfile.processor`

**Changed from:**
```dockerfile
"huggingface-hub>=0.20.0" \
```

**Changed to:**
```dockerfile
"huggingface-hub>=0.16.4,<0.20.0" \
```

**Why this works:**
- Versions `0.16.4` to `0.19.x` still accept `use_auth_token` as a deprecated parameter
- They show deprecation warnings but don't fail
- This allows `pyannote.audio` 3.1.1's internal code to work correctly
- The environment variable approach (`HF_TOKEN`) still works as a fallback

## Version Compatibility Matrix

| Component | Version | Status |
|-----------|---------|--------|
| `pyannote.audio` | 3.1.1 | ✅ Uses `use_auth_token` internally |
| `huggingface-hub` | 0.16.4 - 0.19.x | ✅ Accepts `use_auth_token` (deprecated) |
| `huggingface-hub` | >= 0.20.0 | ❌ Removed `use_auth_token` completely |

## Combined Solution

We're using a **two-pronged approach**:

1. **Version Pinning:** Pin `huggingface-hub` to `<0.20.0` to maintain compatibility
2. **Environment Variables:** Set `HF_TOKEN` and `HUGGING_FACE_HUB_TOKEN` for automatic authentication

This ensures:
- ✅ `pyannote.audio` 3.1.1's internal calls work (uses `use_auth_token`)
- ✅ Environment variable authentication works as fallback
- ✅ No API version conflicts

## Deployment Status

✅ **Code Fixed:** Version constraint updated  
✅ **Committed:** Changes committed to git  
⏳ **Building:** Docker image being rebuilt  
⏳ **Deploying:** Lambda will be updated after build completes  

## Testing

After deployment, verify:
1. Diarization model loads successfully
2. No `use_auth_token` errors in logs
3. Processing completes successfully

## Expected Logs

✅ **Success:**
- `Loading diarization model: pyannote/speaker-diarization-3.1`
- `Diarization model loaded successfully`
- `Diarization complete: X segments, Y unique speakers`

❌ **No longer see:**
- `TypeError: hf_hub_download() got an unexpected keyword argument 'use_auth_token'`
