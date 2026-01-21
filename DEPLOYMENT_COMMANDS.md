# Exact Deployment Commands - AWS Staging

**Date:** 2026-01-20  
**Purpose:** Fix video processor Lambda and import RDS into Terraform

---

## Files Changed

### New Files Created:
1. **`Dockerfile.processor`** - Container image for video processor Lambda
2. **`lambda_handler_processor.py`** - Lambda entry point for container
3. **`infrastructure/ecr.tf`** - ECR repository resource
4. **`scripts/build_and_push_processor_image.sh`** - Build and push script
5. **`COMPLETE_DEPLOYMENT_STEPS.md`** - Detailed deployment guide

### Files Modified:
1. **`infrastructure/lambda.tf`** - Changed from zip to container image
2. **`infrastructure/main.tf`** - Added ECR permissions to IAM role
3. **`infrastructure/outputs.tf`** - Added ECR and Lambda processor outputs

---

## Exact Terminal Commands

### Step 1: Create ECR Repository

```bash
cd /Users/chenjackie/Desktop/LifeStream/infrastructure
terraform apply -target=aws_ecr_repository.lambda_processor -auto-approve
```

**Expected Output:**
```
aws_ecr_repository.lambda_processor: Creating...
aws_ecr_repository.lambda_processor: Creation complete after 2s
```

### Step 2: Build and Push Container Image

```bash
cd /Users/chenjackie/Desktop/LifeStream
./scripts/build_and_push_processor_image.sh
```

**Expected Output:**
```
✅ Image pushed successfully!
   Image URI: 533267430850.dkr.ecr.us-east-1.amazonaws.com/lifestream-lambda-processor-staging:latest
```

**Note:** This script will:
- Login to ECR
- Build Docker image using `Dockerfile.processor`
- Tag and push to ECR repository

### Step 3: Update Lambda Function to Use Container Image

```bash
cd /Users/chenjackie/Desktop/LifeStream/infrastructure
terraform apply -auto-approve
```

**Expected Changes:**
- Lambda function will be updated to use `package_type = "Image"`
- Image URI will point to ECR repository

### Step 4: Import and Reconcile RDS Instance

```bash
cd /Users/chenjackie/Desktop/LifeStream/infrastructure

# Check RDS instance exists and is available
aws rds describe-db-instances --db-instance-identifier lifestream-db-staging --query 'DBInstances[0].[DBInstanceStatus,EngineVersion,DBInstanceClass,AllocatedStorage,StorageType]' --output table

# Import into Terraform state (already done, but verify)
terraform import aws_db_instance.main lifestream-db-staging

# Check for any configuration drift
terraform plan -target=aws_db_instance.main

# If changes needed, update main.tf to match actual RDS settings, then:
terraform apply -target=aws_db_instance.main -auto-approve
```

**Note:** RDS instance was already imported, but verify it's in sync.

### Step 5: Verify All Deployments

```bash
cd /Users/chenjackie/Desktop/LifeStream/infrastructure

# Get ECR repository URL
terraform output -raw ecr_repository_url

# Verify Lambda function is using container image
aws lambda get-function --function-name lifestream-video-processor-staging --query 'Configuration.[FunctionName,State,PackageType,Code.ImageUri]' --output table

# Verify SQS event source mapping
aws lambda list-event-source-mappings --function-name lifestream-video-processor-staging --query 'EventSourceMappings[0].[UUID,State,EventSourceArn]' --output table

# Check Lambda logs (if any)
aws logs tail /aws/lambda/lifestream-video-processor-staging --since 5m --format short

# Test API health endpoint
curl https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging/health
```

---

## All-in-One Command Sequence

```bash
# Set working directory
cd /Users/chenjackie/Desktop/LifeStream/infrastructure

# Step 1: Create ECR repository
terraform apply -target=aws_ecr_repository.lambda_processor -auto-approve

# Step 2: Build and push image
cd ..
./scripts/build_and_push_processor_image.sh

# Step 3: Deploy Lambda with container image
cd infrastructure
terraform apply -auto-approve

# Step 4: Verify RDS is imported (already done)
terraform import aws_db_instance.main lifestream-db-staging || echo "Already imported"

# Step 5: Reconcile RDS config (if needed)
terraform plan -target=aws_db_instance.main
# Review output and apply if changes are acceptable
# terraform apply -target=aws_db_instance.main -auto-approve

# Step 6: Verify deployment
terraform output api_gateway_url
terraform output ecr_repository_url
aws lambda get-function --function-name lifestream-video-processor-staging --query 'Configuration.[FunctionName,State,PackageType]' --output table
```

---

## Expected Results

After completing all steps:

### ✅ ECR Repository
- **Name:** `lifestream-lambda-processor-staging`
- **URI:** `533267430850.dkr.ecr.us-east-1.amazonaws.com/lifestream-lambda-processor-staging`

### ✅ Lambda Function
- **Name:** `lifestream-video-processor-staging`
- **Package Type:** `Image`
- **State:** `Active`
- **Image URI:** Points to ECR repository `:latest`

### ✅ SQS Event Source Mapping
- **State:** `Enabled`
- **Event Source:** SQS queue `lifestream-video-processing-staging`
- **Batch Size:** 1

### ✅ RDS Instance
- **Name:** `lifestream-db-staging`
- **Status:** In Terraform state
- **Config:** Matched with actual instance

---

## Troubleshooting Commands

### If ECR Login Fails:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 533267430850.dkr.ecr.us-east-1.amazonaws.com
```

### If Docker Build Fails:
```bash
cd /Users/chenjackie/Desktop/LifeStream
docker build -f Dockerfile.processor -t test-image .
# Check error messages and fix Dockerfile
```

### If Lambda Update Fails:
```bash
# Check image exists in ECR
aws ecr describe-images --repository-name lifestream-lambda-processor-staging

# Check Lambda current state
aws lambda get-function --function-name lifestream-video-processor-staging
```

### If RDS Import Fails:
```bash
# Check RDS exists
aws rds describe-db-instances --db-instance-identifier lifestream-db-staging

# Check current Terraform state
terraform state show aws_db_instance.main
```

---

## Summary of Changes

| Component | Change | Status |
|-----------|--------|--------|
| Video Processor Lambda | Converted to container image | ✅ Ready |
| ECR Repository | Created | ✅ Ready |
| Dockerfile | Created | ✅ Ready |
| Build Script | Created | ✅ Ready |
| Terraform Config | Updated | ✅ Ready |
| RDS Import | Imported | ✅ Done |
| IAM Permissions | ECR access added | ✅ Ready |

---

**Status:** ✅ All configuration complete, ready to deploy  
**Last Updated:** 2026-01-20
