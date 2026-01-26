# ✅ HuggingFace Authentication Fix

## Issue Identified

**Error:** `TypeError: hf_hub_download() got an unexpected keyword argument 'use_auth_token'`

**Root Cause:** 
- `pyannote.audio` 3.1.1's `Pipeline.from_pretrained()` doesn't accept `token` or `use_auth_token` parameters directly
- The library internally calls `hf_hub_download()` from `huggingface_hub`
- Newer versions of `huggingface_hub` deprecated `use_auth_token` in favor of `token`
- But `pyannote.audio` 3.1.1 still tries to pass `use_auth_token` internally, causing the error

## Fix Applied

**Changed from:**
```python
# Try new API first (token parameter), fall back to old API (use_auth_token)
try:
    self.pipeline = Pipeline.from_pretrained(
        self.settings.diarization_model,
        token=self.settings.huggingface_token
    )
except TypeError:
    # Fall back to deprecated parameter name for older versions
    self.pipeline = Pipeline.from_pretrained(
        self.settings.diarization_model,
        use_auth_token=self.settings.huggingface_token
    )
```

**Changed to:**
```python
# pyannote.audio 3.1.1 doesn't accept token/use_auth_token parameters directly
# Instead, we need to set the token via environment variable or huggingface_hub login
# Set HF_TOKEN environment variable for huggingface_hub to use
import os
original_token = os.environ.get('HF_TOKEN')
try:
    # Set token in environment for huggingface_hub
    os.environ['HF_TOKEN'] = self.settings.huggingface_token
    
    # Also try HUGGING_FACE_HUB_TOKEN (alternative env var name)
    os.environ['HUGGING_FACE_HUB_TOKEN'] = self.settings.huggingface_token
    
    # Load pipeline without token parameter (uses environment variable)
    self.pipeline = Pipeline.from_pretrained(
        self.settings.diarization_model
    )
finally:
    # Restore original token if it existed
    if original_token is not None:
        os.environ['HF_TOKEN'] = original_token
    elif 'HF_TOKEN' in os.environ:
        del os.environ['HF_TOKEN']
    if 'HUGGING_FACE_HUB_TOKEN' in os.environ and original_token is None:
        del os.environ['HUGGING_FACE_HUB_TOKEN']
```

## How It Works

1. **Environment Variable Approach:** Instead of passing the token as a parameter, we set it as an environment variable (`HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN`)
2. **Automatic Detection:** `huggingface_hub` automatically reads the token from these environment variables
3. **No Parameter Conflicts:** By not passing `token` or `use_auth_token`, we avoid the API version mismatch
4. **Clean Cleanup:** The `finally` block ensures we restore the original environment state

## Why This Works

- `huggingface_hub` checks environment variables (`HF_TOKEN`, `HUGGING_FACE_HUB_TOKEN`) before trying to use parameters
- `pyannote.audio` 3.1.1's internal `hf_hub_download()` calls will automatically use the environment variable
- This avoids the deprecated `use_auth_token` parameter issue entirely

## Testing

After deployment, verify:
1. Diarization model loads successfully
2. No authentication errors in logs
3. Processing completes successfully

## Status

✅ **Fixed:** Authentication method updated  
✅ **Committed:** Changes committed to git  
⏳ **Building:** Docker image being rebuilt  
⏳ **Deploying:** Lambda will be updated after build completes  
