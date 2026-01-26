# ECS Processor Deployment

The video processor runs as an **on-demand ECS Fargate task**. A small **dispatcher Lambda** consumes SQS messages and starts one task per job via `RunTask`. API Lambda and API Gateway are unchanged.

## Architecture

- **S3 upload** → SQS message (from S3 event notification and/or API `/upload/confirm`).
- **Dispatcher Lambda** (SQS-triggered):
  - HeadObject for ETag → idempotency check (DynamoDB, keyed by `s3_key|etag`).
  - Conditional PutItem to claim the job; skip if already claimed/processed.
  - Create job record in DynamoDB jobs table.
  - **RunTask** (Fargate) with env overrides: `JOB_ID`, `S3_BUCKET`, `S3_KEY`, etc.
  - **Delete SQS message only after** RunTask succeeds.
- **ECS task** runs the processor container:
  - Reads `JOB_ID`, `S3_BUCKET`, `S3_KEY` from env.
  - Downloads video from S3, runs pipeline (diarization, ASR, scene detection, chunking, summarization).
  - Uploads results to S3, updates job status in DynamoDB, marks idempotency as processed.
  - Exits. Task timeout is enforced in our code, not AWS.

## Terraform Resources

- **ECS**: Cluster, Fargate task definition (4 vCPU, 8 GB), task execution role (ECR, logs), task role (S3, DynamoDB).
- **DynamoDB**: `idempotency` table (existing), `jobs` table for status.
- **Dispatcher Lambda**: Zip deploy, SQS event source, IAM for SQS, S3 HeadObject, DynamoDB, ECS RunTask, PassRole.
- **S3 → SQS** notification for `uploads/` (`.mp4`, `.mov`).
- **CloudWatch**: Log group for ECS tasks (`/ecs/lifestream-processor-<env>`).

## Deploy Steps

1. **Build and push processor image**

   ```bash
   export HF_TOKEN=<your-token>   # for pyannote bake
   ./scripts/build_and_push_processor_image.sh
   ```

   Uses `Dockerfile.processor.ecs`, pushes to the same ECR repo as before.

2. **Apply Terraform**

   ```bash
   cd infrastructure
   terraform plan -out=tfplan
   terraform apply tfplan
   ```

   Creates/updates ECS cluster, task definition, dispatcher Lambda, jobs table, S3→SQS, etc.

3. **Test**

   - Upload a video via the web app (presigned flow → confirm → SQS).
   - Check **Dispatcher** logs: `/aws/lambda/lifestream-dispatcher-<env>`.
   - Check **ECS task** logs: `/ecs/lifestream-processor-<env>`.
   - Verify `results/<job_id>/summary.json` and `summary.md` in S3, and job status if using the jobs table.

## Processor Container

- **Image**: Same ECR repo as before, built from `Dockerfile.processor.ecs`.
- **Entrypoint**: `python -m src.workers.ecs_processor`. Reads `JOB_ID`, `S3_BUCKET`, `S3_KEY`, `WORK_DIR` (default `/tmp`), and table names from env.
- **No Lambda-specific assumptions**: Uses `WORK_DIR` (default `/tmp`); no dependency on Lambda runtime.

## Idempotency

- Key: `(s3_key|etag)`.
- Dispatcher: conditional `PutItem` (claim as “dispatched”) before RunTask; skip if already claimed or processed.
- Processor: `mark_processed` overwrites with “processed” and `result_s3_key` when done.

## SQS and DLQ

- Visibility timeout: 120 s (tuned for dispatcher).
- DLQ configured; failed messages after max retries go to DLQ.
