# Processor Log Fixes and Processing Time

## Issues Addressed

### 1. `[ERROR] VideoManager is deprecated and will be removed`
- **Fix:** Replaced deprecated `VideoManager` with `open_video()` + `SceneManager` in `src/video/scene_detection.py`.
- **Ref:** [scenedetect migration guide](https://www.scenedetect.com/docs/latest/api/migration_guide.html).

### 2. `NumbaSystemWarning: Could not obtain multiprocessing lock ... /dev/shm`
- **Cause:** Lambda has no `/dev/shm`; numba/librosa use multiprocessing.
- **Fix:** In `lambda_handler_processor.py` (before any imports):
  - `NUMBA_NUM_THREADS=1`, `NUMBA_THREADING_LAYER=workqueue`, `NUMBA_WARNINGS=0`
  - `warnings.filterwarnings("ignore", message=".*multiprocessing lock.*")`

### 3. `librosa not available, using file path (may fail with torchcodec issues)`
- **Fix:** Numba env vars above improve librosa import. Diarization fallback now catches `Exception` (not just `ImportError`), logs the real error, and falls back to file path.

### 4. Duplicate processing (same video processed twice)
- **Cause:** Each upload produced **two** SQS messages: (1) S3 `ObjectCreated` → SQS, (2) API `/confirm` → `send_processing_job`. Two Lambdas ran per video.
- **Fix:** Removed `aws_s3_bucket_notification.video_upload_trigger` in `infrastructure/main.tf`. Processing is triggered **only** by API confirm. Apply Terraform to remove S3→SQS notifications.

### 5. `[h264 @ 0x...] mmco: unref short failure`
- **Cause:** FFmpeg/libav decode warnings during scene detection (OpenCV backend). Benign.
- **Fix:** Set `AV_LOG_LEVEL=-8` in processor env to suppress. Our explicit `ffmpeg` calls already use `capture_output=True`.

---

## Why did a “2-minute” video take ~5+ minutes?

1. **Video length:** Logs show **9845 frames @ 29.97 fps ≈ 328 s (~5.5 min)**. The clip is ~5.5 minutes, not 2. Processing at ~6 min is roughly real-time.

2. **Duplicate processing:** Each video was processed by **two** Lambdas (same S3 key, different job IDs). That doubled work and cost. With S3 notifications removed, only one Lambda runs per upload.

3. **Pipeline stages:** Diarization, Whisper ASR, scene detection (~27 s for 9845 frames), summarization, and indexing all add up. Scene detection alone is ~27 s for that length.

**After fixes:** One job per upload, no duplicate work. Runtime should align with video length plus pipeline overhead.

---

## "1:30 video" vs 5.5 min processing (investigation)

If you upload a **1 min 30 sec** video but logs show **~9845 frames @ 29.97 fps (~5.5 min)**, possible causes:

1. **Format vs actual duration mismatch**  
   Container `format=duration` can be wrong (e.g. fragmented MP4, edit lists). We now:
   - Probe `stream=nb_frames,duration` and use **frame-derived duration** when it disagrees with format duration by >15%.
   - Log `"Duration mismatch: format=Xs, stream frames=N @ fps => Ys. Using frame-derived duration."` when that happens.

2. **Diagnostic logging**  
   - **Processor:** Logs `Downloaded job_id=... s3_key=... local_size=... path=...` and, when provided, `client_duration_seconds=...`.
   - **Processor:** After processing, if `client_duration_seconds` was sent and differs from server (ffprobe) duration by >20%, logs  
     `"Duration mismatch: client=Xs, server=Ys (diff=Z%). Possible wrong file or format vs stream duration mismatch."`
   - **Media processor:** Logs `Extracted metadata: duration=Xs, WxH, fps, size=... bytes, nb_frames=...` (when available).

3. **Client-side duration**  
   The frontend now reads duration from the selected video (via `<video>`), sends it as `metadata.client_duration_seconds` on confirm, and the processor compares it to ffprobe. Use this to confirm whether the **uploaded file** matches what you expect.

**Next steps for you:**  
Re-upload a 1:30 video and check CloudWatch for:
- `client_duration_seconds=90` (or ~90).
- `Extracted metadata: duration=...` and any `Duration mismatch` warning.
- `Downloaded ... local_size=...` to confirm we’re processing the right object.

---

## Deploying the fixes

1. **Processor image:** Rebuild and push, then update the processor Lambda.
2. **Infrastructure:** `cd infrastructure && terraform apply` to remove S3→SQS notifications.
