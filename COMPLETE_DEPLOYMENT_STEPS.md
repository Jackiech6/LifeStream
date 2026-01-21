# Complete Deployment Steps - AWS Staging

**Date:** 2026-01-20  
**Environment:** Staging

---

## Summary of Changes

### Files Created/Modified:

1. **Dockerfile.processor** (NEW)
   - Container image for video processor Lambda
   - Uses AWS Lambda Python 3.11 base image
   - Includes FFmpeg and all dependencies

2. **lambda_handler_processor.py** (NEW)
   - Lambda entry point for container image

3. **infrastructure/ecr.tf** (NEW)
   - ECR repository for Lambda container images
   - Lifecycle policy to keep last 10 images

4. **infrastructure/lambda.tf** (MODIFIED)
   - Changed from zip package to container image
   - Uses `package_type = "Image"` and ECR image URI

5. **infrastructure/main.tf** (MODIFIED)
   - Added ECR permissions to Lambda processor IAM role

6. **infrastructure/outputs.tf** (MODIFIED)
   - Added ECR repository URL output
   - Added Lambda processor function name output

7. **scripts/build_and_push_processor_image.sh** (NEW)
   - Script to build and push Docker image to ECR

---

## Step-by-Step Deployment Commands

### Step 1: Create ECR Repository

```bash
cd /Users/chenjackie/Desktop/LifeStream/infrastructure
terraform init
terraform apply -target=aws_ecr_repository.lambda_processor -auto-approve
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

### Step 3: Update Lambda Function to Use Container Image

```bash
cd /Users/chenjackie/Desktop/LifeStream/infrastructure
terraform apply -auto-approve
```

### Step 4: Import and Reconcile RDS Instance

```bash
cd /Users/chenjackie/Desktop/LifeStream/infrastructure

# Check RDS instance status
aws rds describe-db-instances --db-instance-identifier lifestream-db-staging --query 'DBInstances[0].[DBInstanceStatus,EngineVersion,DBInstanceClass,AllocatedStorage]' --output table

# Wait for RDS to be available (if still modifying)
# Once available, run:
terraform import aws_db_instance.main lifestream-db-staging

# Check what Terraform wants to change
terraform plan -target=aws_db_instance.main

# If there are differences, update Terraform config to match actual RDS settings
# Then apply:
terraform apply -target=aws_db_instance.main -auto-approve
```

### Step 5: Verify Deployment

```bash
cd /Users/chenjackie/Desktop/LifeStream/infrastructure

# Check Lambda function
aws lambda get-function --function-name lifestream-video-processor-staging --query 'Configuration.[FunctionName,State,LastModified,PackageType,CodeSize]' --output table

# Check ECR image
aws ecr describe-images --repository-name lifestream-lambda-processor-staging --query 'imageDetails[0].[imageTags,pushedAt,imageSizeInBytes]' --output table

# Check SQS event source mapping
aws lambda list-event-source-mappings --function-name lifestream-video-processor-staging --query 'EventSourceMappings[0].[UUID,State,EventSourceArn]' --output table

# Test by sending a test message to SQS (optional)
# aws sqs send-message --queue-url $(terraform output -raw sqs_queue_url) --message-body '{"test": true}'
```

---

## All-in-One Deployment Script

```bash
#!/bin/bash
# Complete deployment script

cd /Users/chenjackie/Desktop/LifeStream/infrastructure

# Step 1: Create ECR repository
echo "Step 1: Creating ECR repository..."
terraform apply -target=aws_ecr_repository.lambda_processor -auto-approve

# Step 2: Build and push image
echo ""
echo "Step 2: Building and pushing container image..."
cd ..
./scripts/build_and_push_processor_image.sh

# Step 3: Deploy Lambda with container image
echo ""
echo "Step 3: Deploying Lambda function..."
cd infrastructure
terraform apply -auto-approve

# Step 4: Verify deployment
echo ""
echo "Step 4: Verifying deployment..."
echo "Lambda Function:"
aws lambda get-function --function-name lifestream-video-processor-staging --query 'Configuration.FunctionName' --output text

echo "ECR Repository:"
terraform output -raw ecr_repository_url

echo ""
echo "✅ Deployment complete!"
```

---

## Troubleshooting

### Issue: ECR Repository Not Found
```bash
# Create it first
terraform apply -target=aws_ecr_repository.lambda_processor -auto-approve
```

### Issue: Docker Build Fails
```bash
# Check Docker is running
docker ps

# Check Dockerfile exists
ls -la Dockerfile.processor

# Build manually to see errors
docker build -f Dockerfile.processor -t test-image .
```

### Issue: Lambda Function Update Fails
```bash
# Check image URI is correct
terraform output ecr_repository_url

# Verify image exists in ECR
aws ecr describe-images --repository-name lifestream-lambda-processor-staging

# Check Lambda function state
aws lambda get-function --function-name lifestream-video-processor-staging
```

### Issue: RDS Import Fails
```bash
# Check RDS status
aws rds describe-db-instances --db-instance-identifier lifestream-db-staging

# Wait for status to be "available"
# Then import
terraform import aws_db_instance.main lifestream-db-staging

# If Terraform wants to change settings, update main.tf to match actual RDS config
```

---

## Verification Checklist

- [ ] ECR repository created
- [ ] Docker image built and pushed to ECR
- [ ] Lambda function updated to use container image
- [ ] Lambda function state is "Active"
- [ ] SQS event source mapping is "Enabled"
- [ ] IAM permissions include ECR access
- [ ] RDS instance imported and reconciled
- [ ] All Terraform resources in sync

---

## Expected Resources After Deployment

1. **ECR Repository:** `lifestream-lambda-processor-staging`
2. **Lambda Function:** `lifestream-video-processor-staging` (Container Image)
3. **Lambda Event Source Mapping:** SQS queue → Lambda function
4. **IAM Role:** Includes ECR permissions
5. **RDS Instance:** `lifestream-db-staging` (in Terraform state)

---

**Last Updated:** 2026-01-20  
**Status:** Ready for deployment
