#!/bin/bash
# Deploy LifeStream API to AWS Lambda + API Gateway

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "========================================="
echo "LifeStream API Deployment Script"
echo "Lambda + API Gateway"
echo "========================================="
echo "AWS Region: $AWS_REGION"
echo ""

# Step 1: Build Lambda package
echo "Step 1: Building Lambda package..."
./scripts/build_lambda_api_package.sh

if [ $? -ne 0 ]; then
    echo "❌ Lambda package build failed"
    exit 1
fi

echo "✅ Lambda package built successfully"
echo ""

# Step 2: Deploy infrastructure
echo "Step 2: Deploying infrastructure..."
cd "$INFRA_DIR"

# Check if Terraform is initialized
if [ ! -d ".terraform" ]; then
    echo "Initializing Terraform..."
    terraform init
fi

# Apply infrastructure
echo "Applying Terraform configuration..."
terraform apply -auto-approve

if [ $? -ne 0 ]; then
    echo "❌ Terraform apply failed"
    exit 1
fi

echo "✅ Infrastructure deployed"
echo ""

# Step 3: Get API Gateway URL
echo "Step 3: Deployment complete!"
echo ""
API_URL=$(terraform output -raw api_gateway_url 2>/dev/null || echo "N/A")
HEALTH_URL=$(terraform output -raw api_health_check_url 2>/dev/null || echo "N/A")
DOCS_URL=$(terraform output -raw api_docs_url 2>/dev/null || echo "N/A")

echo "========================================="
echo "Deployment Summary"
echo "========================================="
echo "Lambda Function: $(terraform output -raw lambda_api_function_name)"
echo "API Gateway URL: $API_URL"
echo "Health Check: $HEALTH_URL"
echo "API Docs: $DOCS_URL"
echo ""
echo "Test the API:"
echo "  curl $HEALTH_URL"
echo "  curl $API_URL/docs"
echo ""
