# Operations Guide (Staging)

## 1. Deterministic Test Video

- **Local path:** `test_assets/test_5s.mp4`
- **S3 staging path:** `s3://lifestream-videos-staging-533267430850/tests/test_5s.mp4` (uploaded indirectly via API upload jobs)

### Generate locally (if missing)

```bash
cd /Users/chenjackie/Desktop/LifeStream
mkdir -p test_assets
ffmpeg -y \
  -f lavfi -i testsrc=duration=5:size=640x360:rate=25 \
  -f lavfi -i sine=frequency=1000:duration=5 \
  -c:v libx264 -c:a aac \
  test_assets/test_5s.mp4
```

If `ffmpeg` is not installed on macOS:

```bash
brew install ffmpeg
```

The file is **not committed to Git**; it is generated on demand by the E2E script.

## 2. End-to-End Staging Test

### Script

- **Script:** `scripts/staging_e2e_test.sh`
- **Purpose:** Runs a full E2E test against staging (API + S3 + SQS + processor Lambda + vector search).

### What it does

1. Ensures `test_assets/test_5s.mp4` exists; if not, generates it with `ffmpeg`.
2. Calls `terraform output` to discover the staging API Gateway URL.
3. Uploads the test video via `POST /api/v1/upload`.
4. Extracts `job_id` from the upload response.
5. Polls `GET /api/v1/status/{job_id}` until the job is `completed` or `failed` (with timeout).
6. Fetches `GET /api/v1/summary/{job_id}`.
7. Sends a semantic search request to `POST /api/v1/query`.
8. Prints **PASS/FAIL** and exits non-zero on failure.

### How to run

```bash
cd /Users/chenjackie/Desktop/LifeStream
./scripts/staging_e2e_test.sh
```

- Exit code `0` = **PASS**
- Non-zero exit code = **FAIL** (check the echoed JSON responses and CloudWatch logs).

## 3. Deployment (API + Processor)

### Build and push images

```bash
cd /Users/chenjackie/Desktop/LifeStream

# API Lambda image
./scripts/build_and_push_api_image.sh

# Processor Lambda image
./scripts/build_and_push_processor_image.sh
```

### Apply Terraform (staging)

```bash
cd /Users/chenjackie/Desktop/LifeStream/infrastructure
terraform apply -auto-approve
```

This updates:
- API Lambda (container image) and API Gateway
- Processor Lambda (container image)
- S3, SQS, RDS
- CloudWatch alarms and log groups

## 4. Monitoring & Alarms

### CloudWatch Log Groups

- API Lambda: `/aws/lambda/lifestream-api-staging`
- Processor Lambda: `/aws/lambda/lifestream-video-processor-staging`

### Key Alarms (staging)

- **API Lambda Errors:** `lifestream-lambda-api-errors-staging`
  - Metric: `AWS/Lambda`, `Errors`
  - Threshold: > 5 errors over 2×300s periods
- **API Lambda Duration:** `lifestream-lambda-api-duration-staging`
  - Metric: `AWS/Lambda`, `Duration` (Average)
  - Threshold: > 25,000 ms over 2×300s periods
- **API Lambda Throttles:** `lifestream-lambda-api-throttles-staging`
  - Metric: `AWS/Lambda`, `Throttles`
  - Threshold: > 0 over 2×300s periods
- **Processor Lambda Errors:** `lifestream-lambda-processor-errors-staging`
  - Metric: `AWS/Lambda`, `Errors`
  - Threshold: > 1 over 2×300s periods
- **Processor Lambda Throttles:** `lifestream-lambda-processor-throttles-staging`
  - Metric: `AWS/Lambda`, `Throttles`
  - Threshold: > 0 over 2×300s periods
- **Processor Lambda Duration (p95):** `lifestream-lambda-processor-duration-p95-staging`
  - Metric: `AWS/Lambda`, `Duration` (p95)
  - Threshold: ~90% of configured timeout
- **SQS Backlog:** `lifestream-sqs-backlog-staging`
  - Metric: `AWS/SQS`, `ApproximateNumberOfMessagesVisible` (main queue)
  - Threshold: > 0 over 2×300s periods
- **SQS DLQ Messages:** `lifestream-sqs-dlq-messages-staging`
  - Metric: `AWS/SQS`, `ApproximateNumberOfMessagesVisible` (DLQ)
  - Threshold: > 0 over 1×300s period

All alarms send notifications to the configured SNS topic when `enable_billing_alerts` and `notification_email` are set.

## 5. Cost & Hygiene Guardrails

### ECR

- ECR lifecycle policies keep only the **last 10 images** for each repo:
  - `lifestream-lambda-processor-staging`
  - `lifestream-lambda-api-staging`

### S3

- S3 lifecycle configuration for the staging bucket:
  - Bucket: `lifestream-videos-staging-533267430850`
  - All objects (including tests) expire after **30 days**.
  - Non-current versions expire after **7 days**.

### Bucket & Prefix Conventions

- Staging bucket: `lifestream-videos-staging-533267430850`
- Uploads: `uploads/<random-id>.mp4` (managed by API)
- Results: `results/<job_id>/summary.json` and `summary.md`
- Test uploads: created via the E2E script; treated the same as normal uploads.

## 6. Common Failure Modes

- **API returns 500 /health:**
  - Check `/aws/lambda/lifestream-api-staging` logs for import errors (e.g., missing deps).
  - Verify container image build (API) succeeded.
- **Jobs stuck in "queued" state:**
  - Check processor Lambda logs.
  - Check `sqs_backlog` and `sqs_dlq_messages` alarms.
- **Processor fails with S3 404:**
  - Ensure the test video exists in S3.
  - Re-run the E2E script to regenerate and upload.
- **High Lambda duration or throttling:**
  - Inspect `lambda_*_duration` and `lambda_*_throttles` alarms.
  - Consider increasing memory or optimizing processing.

