# Staging Deployment Guide

**Target:** AWS Staging Environment  
**Date:** 2026-01-20  
**Components:** Lambda + API Gateway

---

## Prerequisites

### 1. AWS Credentials Configuration

**Option A: AWS CLI Configure (Recommended)**
```bash
aws configure
# Enter:
# - AWS Access Key ID: [your-access-key]
# - AWS Secret Access Key: [your-secret-key]
# - Default region name: us-east-1
# - Default output format: json
```

**Option B: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_DEFAULT_REGION="us-east-1"
```

**Option C: AWS Profile**
```bash
aws configure --profile staging
# Then use: export AWS_PROFILE=staging
```

**Verify Credentials:**
```bash
aws sts get-caller-identity
```

---

## Deployment Steps

### Automatic Deployment (Recommended)

```bash
# Run the deployment script
./scripts/deploy_staging.sh
```

The script will:
1. ✅ Verify AWS credentials
2. ✅ Build Lambda deployment package
3. ✅ Update terraform.tfvars to staging
4. ✅ Initialize Terraform (if needed)
5. ✅ Run Terraform plan
6. ✅ Apply Terraform configuration
7. ✅ Output API Gateway URL
8. ✅ Verify deployment with /health endpoint

---

### Manual Deployment

If you prefer to run commands manually:

#### Step 1: Build Lambda Package
```bash
cd /Users/chenjackie/Desktop/LifeStream
./scripts/build_lambda_api_package.sh
```

**Expected Output:**
```
✅ Lambda API package created: infrastructure/lambda_api_package.zip
   Size: 21M
```

#### Step 2: Update Environment Configuration
```bash
cd infrastructure
# Verify environment is set to staging
grep "environment" terraform.tfvars
# Should show: environment  = "staging"
```

**File Updated:** `infrastructure/terraform.tfvars`
- Changed: `environment = "dev"` → `environment = "staging"`

#### Step 3: Initialize Terraform
```bash
cd infrastructure
terraform init
```

**Expected Output:**
```
Terraform has been successfully initialized!
```

#### Step 4: Review Terraform Plan
```bash
cd infrastructure
terraform plan -out=tfplan
```

**Review the plan for:**
- Lambda function creation
- API Gateway setup
- IAM roles and policies
- CloudWatch log groups
- S3 bucket (if not exists)

#### Step 5: Apply Terraform Configuration
```bash
cd infrastructure
terraform apply tfplan
```

**Or use auto-approve:**
```bash
terraform apply -auto-approve
```

**Expected Duration:** 2-5 minutes

#### Step 6: Retrieve API Gateway URL
```bash
cd infrastructure
terraform output api_gateway_url
terraform output api_health_check_url
terraform output api_docs_url
```

**Example Output:**
```
api_gateway_url = "https://abc123xyz.execute-api.us-east-1.amazonaws.com/staging"
api_health_check_url = "https://abc123xyz.execute-api.us-east-1.amazonaws.com/staging/health"
api_docs_url = "https://abc123xyz.execute-api.us-east-1.amazonaws.com/staging/docs"
```

#### Step 7: Verify Deployment
```bash
# Wait 10-30 seconds for API Gateway to propagate
sleep 15

# Test health endpoint
curl https://[api-id].execute-api.us-east-1.amazonaws.com/staging/health

# Expected response:
# {"status":"healthy"}
```

---

## Complete Command Sequence

```bash
# 1. Build Lambda package
cd /Users/chenjackie/Desktop/LifeStream
./scripts/build_lambda_api_package.sh

# 2. Navigate to infrastructure
cd infrastructure

# 3. Update to staging (if not already done)
sed -i '' 's/environment.*=.*"dev"/environment  = "staging"/' terraform.tfvars

# 4. Initialize Terraform (first time only)
terraform init

# 5. Plan and apply
terraform plan -out=tfplan
terraform apply tfplan

# 6. Get API URL
terraform output api_gateway_url
terraform output api_health_check_url

# 7. Verify deployment
API_URL=$(terraform output -raw api_gateway_url)
curl "$API_URL/health"
```

---

## Files Modified

### 1. `infrastructure/terraform.tfvars`
**Change:**
```hcl
environment = "dev"  # Before
environment = "staging"  # After
```

**Purpose:** Sets the deployment environment to staging, which affects:
- Resource naming (e.g., `lifestream-api-staging`)
- API Gateway stage name
- Lambda function name

### 2. `infrastructure/lambda_api_package.zip`
**Generated:** Lambda deployment package
- **Size:** ~21 MB
- **Contains:** FastAPI app, Mangum adapter, all dependencies
- **Built by:** `scripts/build_lambda_api_package.sh`

---

## Verification Checklist

After deployment, verify:

- [ ] Lambda package exists (`infrastructure/lambda_api_package.zip`)
- [ ] Terraform initialized (`.terraform/` directory exists)
- [ ] Terraform plan shows expected changes
- [ ] Terraform apply completed successfully
- [ ] API Gateway URL is accessible
- [ ] Health endpoint returns 200: `{"status":"healthy"}`
- [ ] API documentation is accessible
- [ ] Lambda function is active in AWS Console

---

## Expected Infrastructure

### Resources Created

1. **Lambda Function**
   - Name: `lifestream-api-staging`
   - Runtime: Python 3.11
   - Timeout: 900 seconds (15 minutes)
   - Memory: 3008 MB
   - Handler: `lambda_handler.handler`

2. **API Gateway**
   - Type: REST API
   - Stage: `staging`
   - Integration: Lambda proxy

3. **IAM Role**
   - Name: `lifestream-api-lambda-role-staging`
   - Permissions: S3, SQS, Secrets Manager, CloudWatch Logs

4. **CloudWatch Log Group**
   - Name: `/aws/lambda/lifestream-api-staging`
   - Retention: 7 days

---

## Troubleshooting

### Issue: AWS Credentials Not Found
```
Error: No valid credential sources found
```

**Solution:**
```bash
aws configure
# Or set environment variables
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
```

### Issue: Lambda Package Not Found
```
Error: Error uploading lambda package: open lambda_api_package.zip: no such file
```

**Solution:**
```bash
cd /Users/chenjackie/Desktop/LifeStream
./scripts/build_lambda_api_package.sh
```

### Issue: API Gateway Returns 502/503
```
{"message": "Internal server error"}
```

**Solution:**
- Wait 1-2 minutes for API Gateway to propagate
- Check Lambda function logs: `aws logs tail /aws/lambda/lifestream-api-staging --follow`
- Verify Lambda function is deployed correctly

### Issue: Health Endpoint Not Responding
**Solution:**
```bash
# Wait longer for propagation
sleep 30

# Check API Gateway stage
aws apigateway get-stage \
  --rest-api-id <api-id> \
  --stage-name staging

# Check Lambda function
aws lambda get-function --function-name lifestream-api-staging
```

---

## Post-Deployment

### Monitor Logs
```bash
# Follow Lambda logs
aws logs tail /aws/lambda/lifestream-api-staging --follow

# View recent logs
aws logs tail /aws/lambda/lifestream-api-staging --since 5m
```

### Test All Endpoints
```bash
API_URL=$(cd infrastructure && terraform output -raw api_gateway_url)

# Health check
curl "$API_URL/health"

# Root endpoint
curl "$API_URL/"

# Documentation
open "$API_URL/docs"
```

### View in AWS Console
1. **Lambda:** https://console.aws.amazon.com/lambda/
   - Function: `lifestream-api-staging`
   
2. **API Gateway:** https://console.aws.amazon.com/apigateway/
   - API: `lifestream-api-staging`

3. **CloudWatch Logs:** https://console.aws.amazon.com/cloudwatch/
   - Log Group: `/aws/lambda/lifestream-api-staging`

---

## Rollback (if needed)

```bash
cd infrastructure
terraform destroy -target=aws_lambda_function.api
terraform destroy -target=aws_api_gateway_rest_api.api
# Or destroy all resources
terraform destroy
```

---

## Cost Estimate (Staging)

**Monthly Costs:**
- Lambda: ~$0.20 (free tier covers 1M requests)
- API Gateway: ~$0.50 (first 1M requests free)
- CloudWatch Logs: ~$0.10 (first 5GB free)

**Total:** ~$0.80/month (well within free tier)

---

## Next Steps

After successful deployment:

1. ✅ Verify all endpoints are working
2. ✅ Test file upload functionality
3. ✅ Test semantic search (query endpoint)
4. ✅ Monitor CloudWatch logs for errors
5. ✅ Set up CloudWatch alarms (optional)
6. ✅ Configure custom domain (optional)

---

**Deployment Status:** Ready  
**Last Updated:** 2026-01-20  
**Environment:** Staging
