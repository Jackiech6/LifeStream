# Diarization API Fix - DiarizeOutput

## Issue

After fixing the AudioDecoder error with librosa, a new error appeared:
```
AttributeError: 'DiarizeOutput' object has no attribute 'itertracks'
```

## Root Cause

pyannote.audio 3.1 changed the output format. The pipeline now returns a `DiarizeOutput` object instead of an `Annotation` object directly.

## Solution

The `DiarizeOutput` object has an `.annotation` property that returns the `Annotation` object. We need to access this property to get the annotation that has the `itertracks()` method.

## Fix Applied

Modified `src/audio/diarization.py` to:
1. Store pipeline output in `diarization_output` variable
2. Check if it's an `Annotation` object directly
3. If it's a `DiarizeOutput`, access `.annotation` property
4. If it's a dict, access `['annotation']` key
5. Use the resulting `Annotation` object for `itertracks()`

## Code Changes

```python
# Handle pyannote.audio 3.1 output format (DiarizeOutput object)
from pyannote.core import Annotation

if isinstance(diarization_output, Annotation):
    diarization = diarization_output
elif hasattr(diarization_output, 'annotation'):
    diarization = diarization_output.annotation
elif isinstance(diarization_output, dict) and 'annotation' in diarization_output:
    diarization = diarization_output['annotation']
else:
    diarization = diarization_output

# Now use diarization.itertracks() as before
for turn, _, speaker in diarization.itertracks(yield_label=True):
    ...
```

## Status

✅ **FIXED** - The code now handles both `Annotation` and `DiarizeOutput` output formats.
