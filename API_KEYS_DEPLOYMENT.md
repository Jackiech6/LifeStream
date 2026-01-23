# API Keys Deployment Guide

## Overview
This document describes the secure injection of API keys (OpenAI, Pinecone, HuggingFace) into Terraform and their configuration as environment variables for both the API Lambda and Processor Lambda functions.

## Changes Made

### 1. Updated `infrastructure/terraform.tfvars`
- Added `openai_api_key` with the provided OpenAI API key
- Added `huggingface_token` with the provided HuggingFace token
- Added `pinecone_api_key` with the provided Pinecone API key

**Note:** `terraform.tfvars` is gitignored and will never be committed to version control.

### 2. Verified Lambda Environment Variables
Both Lambda functions (API and Processor) are configured with the following environment variables:
- `OPENAI_API_KEY` - For LLM summarization and embeddings
- `HUGGINGFACE_TOKEN` - For speaker diarization models
- `PINECONE_API_KEY` - For vector store operations
- `PINECONE_INDEX_NAME` - Pinecone index name (default: "lifestream-dev")
- `PINECONE_ENVIRONMENT` - Pinecone region (default: "us-east-1")
- `LLM_MODEL` - LLM model to use (default: "gpt-4o")
- `EMBEDDING_MODEL_NAME` - Embedding model (default: "text-embedding-3-small")

### 3. Fixed Environment Variable Consistency
- Made Processor Lambda environment variable configuration consistent with API Lambda
- Added null checks to prevent empty strings from being set

### 4. Added Secrets Manager Permissions
- Added Secrets Manager permissions to Processor Lambda IAM role (for future use)
- Both Lambda functions now have consistent IAM permissions

## Deployment Steps

### Step 1: Verify terraform.tfvars
```bash
cd infrastructure
cat terraform.tfvars | grep -E "(openai_api_key|pinecone_api_key|huggingface_token)"
```

You should see all three API keys configured.

### Step 2: Apply Terraform Changes
```bash
cd infrastructure

# Initialize Terraform (if not already done)
terraform init

# Review changes
terraform plan

# Apply changes
terraform apply
```

This will:
- Update the API Lambda function with new environment variables
- Update the Processor Lambda function with new environment variables
- Update IAM permissions if needed

**Expected output:** Terraform will show that it's updating the Lambda functions' environment variables.

### Step 3: Wait for Lambda Updates
Lambda function updates typically take 1-2 minutes. You can monitor the update status:

```bash
# Get API Lambda update status
aws lambda get-function-configuration \
  --function-name lifestream-api-staging \
  --query 'LastUpdateStatus'

# Get Processor Lambda update status
aws lambda get-function-configuration \
  --function-name lifestream-video-processor-staging \
  --query 'LastUpdateStatus'
```

Wait until both show `"Successful"`.

### Step 4: Verify Deployment
Run the verification script:

```bash
cd scripts
./verify_api_keys.sh
```

This script will:
1. ✅ Check API Gateway health endpoint
2. ✅ Test `/api/v1/query` endpoint (should return 200, not 503)
3. ✅ Verify API keys are set in terraform.tfvars
4. ✅ Check Lambda environment variables via AWS CLI
5. ✅ Test LLM summarization (if processed jobs exist)

## Verification Tests

### Test 1: Query Endpoint (Pinecone Search)
```bash
# Get API Gateway URL
API_URL=$(cd infrastructure && terraform output -raw api_gateway_url)

# Test query endpoint
curl -X POST "$API_URL/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test query",
    "top_k": 5,
    "min_score": 0.0
  }'
```

**Expected:** HTTP 200 response (not 503). The response may have empty results if the index is empty, but it should not return a 503 error.

### Test 2: LLM Summarization End-to-End
```bash
# 1. Upload a video (if not already done)
# Use the presigned URL endpoint or upload directly

# 2. Wait for processing to complete
# Monitor via CloudWatch logs or status endpoint

# 3. Get summary
JOB_ID="your-job-id"
curl "$API_URL/api/v1/summary/$JOB_ID"
```

**Expected:** HTTP 200 with summary containing:
- `summary_markdown` - LLM-generated summary
- `time_blocks` - Structured time blocks
- `video_metadata` - Video information

## Troubleshooting

### Issue: Query endpoint returns 503
**Symptoms:** `/api/v1/query` returns HTTP 503 with message about missing API keys

**Solutions:**
1. Verify terraform.tfvars has all API keys set:
   ```bash
   cd infrastructure
   grep -E "(openai_api_key|pinecone_api_key|huggingface_token)" terraform.tfvars
   ```

2. Re-apply Terraform:
   ```bash
   cd infrastructure
   terraform apply
   ```

3. Verify Lambda environment variables:
   ```bash
   aws lambda get-function-configuration \
     --function-name lifestream-api-staging \
     --query 'Environment.Variables' | grep -E "(OPENAI|PINECONE)"
   ```

4. Wait for Lambda update to complete (check LastUpdateStatus)

### Issue: Summarization fails
**Symptoms:** Video processing completes but summary is empty or missing

**Solutions:**
1. Check CloudWatch logs for Processor Lambda:
   ```bash
   aws logs tail /aws/lambda/lifestream-video-processor-staging --follow
   ```

2. Verify OPENAI_API_KEY is set in Processor Lambda:
   ```bash
   aws lambda get-function-configuration \
     --function-name lifestream-video-processor-staging \
     --query 'Environment.Variables.OPENAI_API_KEY'
   ```

3. Check for errors in the logs related to OpenAI API calls

### Issue: Terraform apply fails
**Solutions:**
1. Ensure you're authenticated to AWS:
   ```bash
   aws sts get-caller-identity
   ```

2. Check Terraform state:
   ```bash
   cd infrastructure
   terraform state list
   ```

3. Verify AWS credentials have necessary permissions

## Security Notes

1. **Never commit terraform.tfvars** - It's in `.gitignore` but always double-check before committing
2. **API keys are stored as environment variables** - They appear in Lambda console and CloudWatch logs (be careful with log sharing)
3. **For production**, consider using AWS Secrets Manager instead of environment variables:
   - Create secrets in Secrets Manager
   - Update Terraform to reference secret ARNs
   - Lambda functions already have Secrets Manager permissions

## Files Modified

- `infrastructure/terraform.tfvars` - Added API keys (gitignored)
- `infrastructure/lambda.tf` - Fixed environment variable consistency
- `infrastructure/main.tf` - Added Secrets Manager permissions to Processor Lambda
- `scripts/verify_api_keys.sh` - New verification script

## Next Steps

After successful deployment:

1. ✅ Run verification script: `./scripts/verify_api_keys.sh`
2. ✅ Test query endpoint with a real query
3. ✅ Upload a test video and verify LLM summarization works end-to-end
4. ✅ Monitor CloudWatch logs for any API key-related errors
5. ✅ Consider migrating to Secrets Manager for production

## Support

If you encounter issues:
1. Check CloudWatch logs for both Lambda functions
2. Run the verification script for diagnostics
3. Verify Terraform outputs match expected values
4. Ensure AWS credentials have proper permissions
