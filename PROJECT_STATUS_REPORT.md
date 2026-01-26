# LifeStream — Project Status Report

**Generated:** January 2025  
**Project:** LifeStream Intelligent Diary — multi-modal video → structured, searchable daily journals and meeting minutes.

---

## 1. Overview

| Item | Status |
|------|--------|
| **Stage** | Stage 1–3 complete (Core pipeline, RAG, Cloud deployment) |
| **Architecture** | API Lambda + API Gateway, **ECS Fargate** processor, dispatcher Lambda, S3, SQS, DynamoDB, Pinecone |
| **Frontend** | Next.js app (upload, jobs, chat, summary) |
| **Local pipeline** | `python src/main.py --input <video> --output summary.md` |

---

## 2. Architecture (Current)

```
┌─────────────────┐     presigned URL      ┌──────────────┐
│  Web frontend   │ ────────────────────►  │  S3 bucket   │
│  (Next.js)      │                        │  (uploads/)  │
└────────┬────────┘                        └──────┬───────┘
         │ confirm + job_id                       │
         ▼                                        │ s3 events
┌─────────────────┐     SQS message              │
│  API Lambda     │ ◄────────────────────────────┘
│  (FastAPI)      │
└────────┬────────┘
         │ SendMessage
         ▼
┌─────────────────┐     RunTask                  ┌─────────────────┐
│  Dispatcher     │ ─────────────────────────►   │  ECS Fargate    │
│  Lambda         │     (1 task per job)         │  processor      │
└─────────────────┘                              └────────┬────────┘
         │                                                 │
         │ idempotency (s3_key|etag)                       │ upload
         ▼                                                 ▼
┌─────────────────┐                              ┌─────────────────┐
│  DynamoDB       │   job status, idempotency    │  S3 results/    │
│  (jobs,         │ ◄────────────────────────────│  Pinecone       │
│   idempotency)  │                              │  index          │
└─────────────────┘                              └─────────────────┘
```

- **API Lambda + API Gateway**: Unchanged. Handles presigned upload, confirm, status, summary, query.
- **Dispatcher Lambda**: Consumes SQS, checks idempotency (DynamoDB), starts **one ECS task per job** via `RunTask`, deletes SQS message only after task is started.
- **ECS Fargate processor**: Runs processor container; downloads from S3, runs pipeline, uploads results, updates job status, exits.

---

## 3. Implemented Features

### 3.1 Pipeline (per onboarding spec)

| Feature | Implementation |
|---------|----------------|
| **Speaker diarization** | pyannote.audio 3.1 (baked in image) |
| **ASR** | faster-whisper (primary) / openai-whisper (fallback) |
| **Scene detection** | PySceneDetect; keyframes at scene boundaries |
| **Chunking** | 5-minute time-based; scenes enrich chunks, not boundaries |
| **LLM summarization** | One ChatGPT call per 5‑min chunk (per-speaker, scene, action items) |
| **Meeting vs non-meeting** | Heuristic-only (no LLM) |

### 3.2 API & frontend

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/upload/presigned-url` | Get presigned URL + `job_id` |
| `POST /api/v1/upload/confirm` | Confirm upload, send job to SQS |
| `GET /api/v1/status/{job_id}` | Job status (S3-based: queued / processing / completed) |
| `GET /api/v1/summary/{job_id}` | JSON or Markdown summary |
| `POST /api/v1/query` | Semantic search + single ChatGPT synthesis over retrieved chunks |

### 3.3 Processing optimizations

- Skip interval frame extraction; use **single ffmpeg** mono 16 kHz WAV for diarization + ASR.
- **Parallel** audio (diarization + ASR) and scene (detection + keyframes) branches; `parallel_max_workers=2`.
- **faster-whisper** for ASR; scene detection **frame skip** (default 2).
- **Baked models** in processor image (no HuggingFace/Whisper downloads at runtime).
- **Idempotency** by `(s3_key, etag)`; conditional DynamoDB claim before RunTask.
- **Per-stage timings** logged: download, audio_extraction, diarization, ASR, scene_detection, keyframes, sync, summarization, upload, indexing.
- **Thread caps** (OMP, MKL, OPENBLAS, NUMBA) to avoid oversubscription.

---

## 4. Infrastructure (Terraform)

| Resource | Purpose |
|----------|---------|
| **S3** | Video uploads, presigned uploads; results (`results/<job_id>/`) |
| **SQS** | Video jobs queue; visibility 120 s; DLQ |
| **S3 → SQS** | Notifications for `uploads/*.mp4`, `uploads/*.mov` |
| **DynamoDB** | `idempotency` (s3_key|etag), `jobs` (status) |
| **ECS** | Cluster, Fargate task def (4 vCPU, 8 GB), task + execution roles |
| **Dispatcher Lambda** | SQS-triggered; RunTask, idempotency, message delete after start |
| **API Lambda** | FastAPI; API Gateway proxy |
| **ECR** | Processor image (used by ECS) |
| **CloudWatch** | Log groups for API, dispatcher, ECS processor tasks |

---

## 5. Deployment

### 5.1 Processor (ECS)

1. **Build and push image**
   ```bash
   export HF_TOKEN=<token>
   ./scripts/build_and_push_processor_image.sh
   ```
   Uses `Dockerfile.processor.ecs`, pushes to ECR.

2. **Terraform**
   ```bash
   cd infrastructure && terraform apply
   ```

3. **Test**: Upload video → dispatcher logs → ECS task logs → `results/<job_id>/*` in S3.

See **ECS_DEPLOYMENT.md** for details.

### 5.2 API

- Build/push API image, deploy Lambda, update API Gateway (e.g. `./scripts/deploy_api.sh` or equivalent).
- Frontend: configure API base URL, build, and deploy (e.g. Vercel or static hosting).

---

## 6. Testing

| Suite | Result |
|-------|--------|
| **Unit tests** | 139 passed, 4 failed, 1 error, 1 skipped |
| **Known failures** | `test_upload_file_*` (S3 upload mock), `test_upload_endpoint_*` (route patch / Settings), `test_upload_endpoint_valid_file` (AttributeError) |
| **Lambda handler** | All 6 tests pass (including idempotent skip) |
| **Integration** | Scripts exist (`comprehensive_e2e_test.sh`, `staging_e2e_test.sh`, etc.); run manually against deployed env |

---

## 7. Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `scene_detection_frame_skip` | 2 | Frame skip for scene detection |
| `use_faster_whisper` | True | Use faster-whisper for ASR |
| `asr_model` | base | Whisper model size |
| `chunk_size_seconds` | 300 | 5-minute chunks |
| `parallel_max_workers` | 2 | Audio ‖ scene parallelism |

---

## 8. Documentation

| Doc | Purpose |
|-----|---------|
| **README.md** | Quick start, stages overview |
| **ECS_DEPLOYMENT.md** | ECS processor + dispatcher deploy |
| **PROCESSING_OPTIMIZATION.md** | Pipeline optimizations |
| **LOCAL_SETUP.md** | Local Mac setup |
| **STAGE1_IMPLEMENTATION_PLAN.md** | Stage 1 architecture |
| **infrastructure/** | Terraform modules, examples |

---

## 9. Pending / Known Gaps

- **Unit tests**: Fix S3 upload and API upload-route mocks/patches so all unit tests pass.
- **Status API**: Still S3-based (queued / processing / completed). Optional: read DynamoDB `jobs` when configured.
- **Task timeout**: Enforced in application code; signal-based or similar logic to be added if required.
- **Production**: Restrict CORS, tighten IAM, use Secrets Manager for API keys in ECS task def, consider ECS placement in private subnets.

---

## 10. Summary

LifeStream implements the full onboarding spec: diarization, ASR, scene detection, 5‑minute chunking, one ChatGPT call per chunk, RAG query with synthesis, and cloud deployment. The **processor runs on ECS Fargate**; a **dispatcher Lambda** handles SQS, idempotency, and RunTask. The **API and Gateway are unchanged**. Processing is optimized (faster-whisper, parallelism, baked models, idempotency, timings). Remaining work is mainly test fixes, optional status/store improvements, and production hardening.
