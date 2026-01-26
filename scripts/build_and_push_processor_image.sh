#!/bin/bash
# Build and push processor container image to ECR for ECS Fargate.
# Processor runs as on-demand ECS task; dispatcher Lambda starts it via RunTask.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AWS_REGION="${AWS_REGION:-us-east-1}"

ECR_REPO_NAME="lifestream-lambda-processor-staging"
ECR_REPO_URI=$(aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$AWS_REGION" --query 'repositories[0].repositoryUri' --output text 2>/dev/null || echo "")

if [ -z "$ECR_REPO_URI" ]; then
    echo "❌ ECR repository not found: $ECR_REPO_NAME"
    echo "   Run 'terraform apply' first to create the ECR repository"
    exit 1
fi

echo "========================================="
echo "Building and Pushing Processor ECS Image"
echo "========================================="
echo "ECR Repository: $ECR_REPO_URI"
echo "AWS Region: $AWS_REGION"
echo ""

echo "Step 1: Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REPO_URI"

echo ""
echo "Step 2: Building and pushing Docker image (Dockerfile.processor.ecs, linux/amd64)..."
cd "$PROJECT_ROOT"
# HF_TOKEN required to bake pyannote models at build time. No HF downloads at runtime.
if [ -z "${HF_TOKEN:-}" ]; then
  echo "   ERROR: HF_TOKEN not set. Set HF_TOKEN and re-run to bake pyannote (build will fail otherwise)."
  exit 1
fi
echo "   Using HF_TOKEN to bake pyannote model (HF_HUB_OFFLINE=1 at runtime)"
docker buildx build --platform linux/amd64 \
  --no-cache \
  --provenance=false \
  --sbom=false \
  --build-arg "HF_TOKEN=$HF_TOKEN" \
  -f Dockerfile.processor.ecs \
  -t "$ECR_REPO_URI:latest" \
  --push .

echo ""
echo "✅ Image pushed successfully!"
echo "   Image URI: $ECR_REPO_URI:latest"
echo ""
echo "Next steps:"
echo "  1. Run 'terraform apply' in infrastructure/"
echo "  2. Upload a video via the app; dispatcher starts ECS task, task writes to S3 and updates status"
echo "  3. Check /ecs/lifestream-processor-<env> CloudWatch log group for task logs"
