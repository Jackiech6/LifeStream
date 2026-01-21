#!/bin/bash
# Build and push API Lambda container image to ECR

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Get ECR repository name from Terraform output or use default
ECR_REPO_NAME="lifestream-lambda-api-staging"
ECR_REPO_URI=$(aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$AWS_REGION" --query 'repositories[0].repositoryUri' --output text 2>/dev/null || echo "")

if [ -z "$ECR_REPO_URI" ]; then
    echo "❌ ECR repository not found: $ECR_REPO_NAME"
    echo "   Run 'terraform apply' first to create the ECR repository"
    exit 1
fi

echo "========================================="
echo "Building and Pushing API Lambda Container Image"
echo "========================================="
echo "ECR Repository: $ECR_REPO_URI"
echo "AWS Region: $AWS_REGION"
echo ""

# Login to ECR
echo "Step 1: Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REPO_URI"

# Build and push image in one step (Lambda requires OCI-compliant images)
# Lambda supports both x86_64 and ARM64 - use x86_64 for compatibility
# Use --provenance=false to avoid creating manifest lists (Lambda doesn't support them)
echo ""
echo "Step 2: Building and pushing Docker image for Lambda (Linux amd64)..."
cd "$PROJECT_ROOT"
docker buildx build --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  -f Dockerfile.api \
  -t "$ECR_REPO_URI:latest" \
  --push .

echo ""
echo "✅ Image pushed successfully!"
echo "   Image URI: $ECR_REPO_URI:latest"
echo ""
echo "Next steps:"
echo "  1. Run 'terraform apply' to update Lambda function"
echo "  2. Verify API: curl https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging/health"
