# Processing Time Optimizations

Goal: **1 hour of video → &lt; 20 minutes processing** (onboarding guideline), while preserving output quality.

## Changes Made

### 1. Skip interval frame extraction

- **Before:** `split_media_tracks` extracted a frame every 5 seconds (e.g. 720 frames for 1 hr) via many ffmpeg calls. These frames were discarded—we use **scene keyframes** only.
- **After:** `split_media_tracks(..., extract_frames=False)` by default. We extract **audio only** and rely on scene detection + keyframes.
- **Impact:** Removes hundreds of ffmpeg invocations per long video.

### 2. Scene detection frame skip

- **Before:** PySceneDetect processed every frame (e.g. ~108k @ 30 fps for 1 hr).
- **After:** `detect_scenes(..., frame_skip=2)` (configurable via `scene_detection_frame_skip`). `frame_skip=2` → every 3rd frame (~3× fewer).
- **Impact:** ~3× faster scene detection with minimal impact (scenes enrich chunks only; boundaries are 5‑minute time-based).

### 3. Parallel audio and scene pipelines

- **Before:** Sequential: media split → diarization → ASR → scene detection → keyframes → sync → …
- **After:** After media split (audio only), we run in parallel:
  - **Audio branch:** diarization → ASR
  - **Scene branch:** scene detection → keyframe extraction  
  Then sync, meeting detection, summarization.
- **Impact:** Wall‑clock time for Phase 3+4 ≈ `max(diarization+ASR, scene_detection+keyframes)` instead of their sum.

### 4. faster-whisper for ASR

- **Before:** OpenAI Whisper (PyTorch) for transcription.
- **After:** **faster-whisper** (CTranslate2) when available; fallback to openai-whisper. Same model weights, ~4× faster inference. `use_faster_whisper` in settings (default `True`).
- **Impact:** ~4× faster ASR at equivalent quality.

## Configuration

| Setting | Default | Description |
|--------|---------|-------------|
| `scene_detection_frame_skip` | `2` | 0=none, 2=every 3rd frame, etc. |
| `use_faster_whisper` | `True` | Use faster-whisper when available |
| `asr_model` | `base` | Whisper model size (tiny, base, small, …) |

## Deployment

- **Processor Lambda:** Rebuild the Docker image (includes `faster-whisper`). Ensure `use_faster_whisper` and `scene_detection_frame_skip` are set via env if you override.
- **Local:** `pip install -r requirements.txt` (adds `faster-whisper`). Run pipeline as before.

## Expected impact

- **1 hr video:** Previously on the order of ~1× realtime or worse (e.g. 60+ min). With these changes, target **&lt; 20 min** assuming typical Lambda CPU and model load times.
- **Short clips (e.g. 2 min):** Noticeably faster due to parallelization, no interval frame extraction, and faster ASR.

## Quality

- **Summarization:** Unchanged (one ChatGPT call per 5‑min chunk).
- **Diarization:** Unchanged (pyannote).
- **ASR:** Same Whisper weights; faster-whisper is a CTranslate2 reimplementation with comparable accuracy.
- **Scene detection:** Slight coarser granularity from frame skip; still used only to enrich 5‑min chunks, not to define boundaries.

---

## Additional optimizations (no runtime downloads, idempotency, timings)

### 5. Baked models (no runtime downloads)

- **Diarization** (pyannote) and **ASR** (faster-whisper base) are baked into the processor image at build time.
- **Build:** `docker build --build-arg HF_TOKEN=<token> -f Dockerfile.processor .`
- **Runtime:** `HF_HOME` / `HF_HUB_CACHE` → `/opt/models/huggingface`, `WHISPER_CACHE_DIR` → `/opt/models/whisper`, `HF_HUB_OFFLINE=1`.

### 6. Idempotency (S3 key + ETag)

- Each `(s3_key, etag)` is processed at most once (DynamoDB). HeadObject → ETag → check → skip or process → mark.

### 7. SQS visibility

- `visibility_timeout_seconds = lambda_timeout + 300` to reduce duplicate delivery.

### 8. Per-stage timings

- Logged: `download`, `audio_extraction`, `diarization`, `asr`, `scene_detection`, `keyframes`, `sync`, `summarization`, `upload`, `indexing`. Full dict in logs and Lambda response.

### 9. Single ffmpeg mono 16 kHz WAV

- One ffmpeg call: mono, 16 kHz WAV for diarization and ASR.

### 10. Thread caps

- `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`. `parallel_max_workers=2` for audio ‖ scene.

### 11. Streaming URL pipeline (ECS)

- **Before:** Download full video from S3 → then run pipeline (audio extraction, scene, etc.).
- **After:** Generate presigned GET URL; start **background download** and **audio extraction from URL** in parallel. FFmpeg streams from the URL for metadata + WAV extraction while the file is written to disk. When download finishes, scene detection and keyframes run on the local file.
- **Impact:** Wall‑clock time hides most of the download inside audio extraction (overlap). Same region + S3 VPC Gateway endpoint keeps S3 traffic fast and off the public internet.
- **Config:** `USE_STREAMING_VIDEO_INTAKE=true` (default) in ECS task; set to `false` to revert to download-then-process.

### 12. Same region and S3 VPC Gateway endpoint

- **S3 bucket** and **ECS tasks** use the same `var.aws_region` (e.g. `us-east-1`) so transfers never cross regions.
- **S3 VPC Gateway endpoint** is created in `infrastructure/main.tf` for the default VPC. ECS task S3 traffic uses the AWS backbone (no NAT gateway, no internet egress for S3). Apply with `terraform apply` so the endpoint is active.

## Configuration (additions)

| Setting / Env | Default | Description |
|---------------|---------|-------------|
| `use_streaming_video_intake` / `USE_STREAMING_VIDEO_INTAKE` | `true` | ECS: overlap download with audio-from-URL |

## Cost impact

- **S3 VPC Gateway endpoint:** No additional charge; can reduce cost by avoiding NAT Gateway data processing for S3.
- **Streaming pipeline:** No new billable resources. Same S3 GET, same ECS task duration (often shorter wall‑clock). Slight increase in concurrent network/CPU during overlap (download + ffmpeg decode) is negligible on existing Fargate task size.
- **Same region:** No cross-region data transfer; keeps S3 and ECS costs predictable.
- **Net:** No expected increase in cost; small decrease possible due to shorter task duration and optional NAT savings.
