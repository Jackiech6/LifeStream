# Backend Redeploy & Lambda Environment Variables Check

## Redeploy Summary

- **API Lambda:** Built and pushed `lifestream-lambda-api-staging:latest`, then updated the function to use it.
- **Processor Lambda:** Updated to use `lifestream-lambda-processor-staging:latest` (previously built).
- **Terraform:** Applied `lambda.tf` to add `HF_HOME` and `HF_HUB_CACHE` to the processor Lambda.

## Lambda Environment Variables Verification

### Processor Lambda (`lifestream-video-processor-staging`)

| Variable | Purpose | Status |
|----------|---------|--------|
| `OPENAI_API_KEY` | LLM summarization, embeddings | ✅ Set (from tfvars) |
| `HUGGINGFACE_TOKEN` | Pyannote diarization models | ✅ Set (from tfvars) |
| `PINECONE_API_KEY` | Vector store indexing | ✅ Set (from tfvars) |
| `AWS_S3_BUCKET_NAME` | Video upload/download | ✅ Set |
| `AWS_SQS_QUEUE_URL` | Job queue | ✅ Set |
| `AWS_SQS_DLQ_URL` | Dead-letter queue | ✅ Set |
| `PINECONE_INDEX_NAME` | Pinecone index | ✅ Set |
| `PINECONE_ENVIRONMENT` | Pinecone region | ✅ Set |
| `LLM_MODEL` | e.g. gpt-4o | ✅ Set |
| `EMBEDDING_MODEL_NAME` | e.g. text-embedding-3-small | ✅ Set |
| `WHISPER_CACHE_DIR` | Whisper model cache in /tmp | ✅ Set |
| `HF_HOME` | HuggingFace cache root | ✅ Set (`/tmp/huggingface`) |
| `HF_HUB_CACHE` | HuggingFace hub cache | ✅ Set (`/tmp/huggingface/hub`) |

### API Lambda (`lifestream-api-staging`)

| Variable | Purpose | Status |
|----------|---------|--------|
| `OPENAI_API_KEY` | Embeddings, query | ✅ Set |
| `HUGGINGFACE_TOKEN` | (if needed by routes) | ✅ Set |
| `PINECONE_API_KEY` | Vector search | ✅ Set |
| `AWS_S3_BUCKET_NAME` | Presigned upload, status | ✅ Set |
| `AWS_SQS_QUEUE_URL` | Job submission | ✅ Set |
| `AWS_SQS_DLQ_URL` | DLQ | ✅ Set |
| `PINECONE_INDEX_NAME` | Pinecone index | ✅ Set |
| `PINECONE_ENVIRONMENT` | Pinecone region | ✅ Set |
| `LLM_MODEL` | — | ✅ Set |
| `EMBEDDING_MODEL_NAME` | — | ✅ Set |

## Terraform / `terraform.tfvars`

API keys and tokens are sourced from `infrastructure/terraform.tfvars`:

- `openai_api_key`
- `huggingface_token`
- `pinecone_api_key`

Terraform passes these into both Lambdas’ environment. Never commit `terraform.tfvars`.

## Health Check

```bash
curl -s "https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging/health"
# {"status":"healthy"}
```

## Re-verify Env Vars (CLI)

```bash
# Processor
aws lambda get-function-configuration --function-name lifestream-video-processor-staging \
  --region us-east-1 --query 'Environment.Variables'

# API
aws lambda get-function-configuration --function-name lifestream-api-staging \
  --region us-east-1 --query 'Environment.Variables'
```

## Changes Made

1. **`infrastructure/lambda.tf`**  
   - Added `HF_HOME` and `HF_HUB_CACHE` to the processor Lambda environment for the HuggingFace cache fix.

2. **Redeploy**  
   - Built and pushed API image; updated both API and processor Lambdas to use latest ECR images.  
   - Applied Terraform for the processor Lambda env updates.

All required environment variables are set correctly for both Lambdas.
