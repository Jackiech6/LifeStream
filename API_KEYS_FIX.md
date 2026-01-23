# API Keys Fix - Environment Variable Reading

## Issue
The Lambda functions have the API keys set in their environment variables (verified via AWS CLI), but the application code is sometimes reporting "Pinecone API key not configured" (503 errors).

## Root Cause
Pydantic BaseSettings should automatically read environment variables, but in Lambda environments, there can be timing or caching issues where the environment variables aren't read correctly on first access.

## Fix Applied
Added explicit fallback environment variable reading in `config/settings.py` to ensure API keys are always read correctly in Lambda:

```python
# In Settings.__init__(), when running in Lambda:
if not self.openai_api_key and os.environ.get("OPENAI_API_KEY"):
    self.openai_api_key = os.environ.get("OPENAI_API_KEY")
if not self.pinecone_api_key and os.environ.get("PINECONE_API_KEY"):
    self.pinecone_api_key = os.environ.get("PINECONE_API_KEY")
if not self.huggingface_token and os.environ.get("HUGGINGFACE_TOKEN"):
    self.huggingface_token = os.environ.get("HUGGINGFACE_TOKEN")
```

This ensures that even if Pydantic doesn't pick up the environment variables initially, they will be read directly from `os.environ` as a fallback.

## Deployment Steps

### Step 1: Rebuild and Push API Lambda Container
```bash
cd scripts
./build_and_push_api_image.sh
```

This will:
- Build a new Docker image with the updated `config/settings.py`
- Push it to ECR with the `latest` tag
- Terraform will automatically pick up the new image on next apply

### Step 2: Update Lambda Function (if needed)
The Lambda function should automatically use the new `latest` image, but you can force an update:

```bash
cd infrastructure
terraform apply
```

This will update the Lambda function to use the latest container image.

### Step 3: Verify the Fix
Wait 1-2 minutes for the Lambda update to complete, then run:

```bash
cd scripts
./verify_api_keys.sh
```

You should see:
- ✅ Query endpoint returns 200 (no 503 errors)
- ✅ Lambda environment variables are correctly detected
- ✅ All API keys are set

## Current Status

✅ **API Keys in Terraform**: All keys are set in `terraform.tfvars`
✅ **Lambda Environment Variables**: Verified via AWS CLI - all keys are present
✅ **Code Fix**: Added explicit environment variable reading fallback
⏳ **Deployment**: Need to rebuild and redeploy Lambda container images

## Verification

After deployment, test the query endpoint:

```bash
API_URL=$(cd infrastructure && terraform output -raw api_gateway_url)
curl -X POST "$API_URL/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5}'
```

Expected: HTTP 200 response (not 503)

## Troubleshooting

If you still see 503 errors after deployment:

1. **Check Lambda Logs**:
   ```bash
   aws logs tail /aws/lambda/lifestream-api-staging --follow --region us-east-1
   ```

2. **Verify Environment Variables**:
   ```bash
   aws lambda get-function-configuration \
     --function-name lifestream-api-staging \
     --region us-east-1 \
     --query 'Environment.Variables' | grep -E "(OPENAI|PINECONE)"
   ```

3. **Check Container Image**:
   ```bash
   aws lambda get-function-configuration \
     --function-name lifestream-api-staging \
     --region us-east-1 \
     --query 'Code.ImageUri'
   ```
   
   Verify it's using the latest image.

4. **Force Lambda Update**:
   ```bash
   aws lambda update-function-code \
     --function-name lifestream-api-staging \
     --region us-east-1 \
     --image-uri <ECR_URI>:latest
   ```

## Files Modified

- `config/settings.py` - Added explicit environment variable reading fallback for Lambda
