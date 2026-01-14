# Diarization AudioDecoder Fix

## Issue

The pipeline was failing with:
```
NameError: name 'AudioDecoder' is not defined
```

This happens because:
1. `pyannote.audio` tries to use `torchcodec` for audio decoding
2. `torchcodec` requires FFmpeg libraries that match specific versions (59, 58, 57, 56)
3. The system has FFmpeg 8.0.1 with libavutil.60, but torchcodec expects older versions
4. When torchcodec fails, `pyannote.audio` has a bug where it still tries to use `AudioDecoder` without proper error handling

## Solution

**Workaround**: Load audio files using `librosa` and pass them as dictionaries to pyannote.audio instead of file paths.

This bypasses the torchcodec/AudioDecoder path entirely and uses pyannote.audio's internal audio handling.

## Implementation

Modified `src/audio/diarization.py` to:
1. Load audio with `librosa` (16000 Hz, mono)
2. Convert to PyTorch tensor
3. Create audio dict: `{"waveform": tensor, "sample_rate": 16000}`
4. Pass dict to pipeline instead of file path

## About Frame Extraction

**Note**: The 5-second frame extraction is **NOT a bug**. This is the intended behavior:
- `extract_video_frames()` extracts frames every 5 seconds by default
- Scene detection (Phase 4) will refine frame selection later
- This is the correct initial extraction strategy
