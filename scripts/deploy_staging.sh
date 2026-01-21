#!/bin/bash
# Deploy LifeStream API to AWS Staging Environment
# Prerequisites: AWS credentials must be configured

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"

echo "========================================="
echo "LifeStream API - Staging Deployment"
echo "========================================="
echo ""

# Check AWS credentials
echo "Step 0: Verifying AWS credentials..."
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS credentials not configured!"
    echo ""
    echo "Please configure AWS credentials first:"
    echo "  1. Run: aws configure"
    echo "  2. Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables"
    echo "  3. Or use: aws configure --profile <profile-name>"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "✅ AWS credentials verified (Account: $ACCOUNT_ID)"
echo ""

# Step 1: Build Lambda package
echo "Step 1: Building Lambda deployment package..."
cd "$PROJECT_ROOT"
./scripts/build_lambda_api_package.sh

if [ ! -f "$INFRA_DIR/lambda_api_package.zip" ]; then
    echo "❌ Lambda package not found: $INFRA_DIR/lambda_api_package.zip"
    exit 1
fi

PACKAGE_SIZE=$(du -h "$INFRA_DIR/lambda_api_package.zip" | cut -f1)
echo "✅ Lambda package built successfully ($PACKAGE_SIZE)"
echo ""

# Step 2: Verify staging configuration
echo "Step 2: Verifying staging configuration..."
cd "$INFRA_DIR"

if ! grep -q 'environment.*=.*"staging"' terraform.tfvars; then
    echo "⚠️  Warning: terraform.tfvars does not have environment = \"staging\""
    echo "   Updating to staging..."
    sed -i '' 's/environment.*=.*"dev"/environment  = "staging"/' terraform.tfvars 2>/dev/null || \
    sed -i 's/environment.*=.*"dev"/environment  = "staging"/' terraform.tfvars
fi

echo "✅ Staging configuration verified"
echo ""

# Step 3: Initialize Terraform
echo "Step 3: Initializing Terraform..."
if [ ! -d ".terraform" ]; then
    terraform init
else
    echo "✅ Terraform already initialized"
fi
echo ""

# Step 4: Terraform Plan
echo "Step 4: Running Terraform plan..."
terraform plan -out=tfplan

if [ $? -ne 0 ]; then
    echo "❌ Terraform plan failed"
    exit 1
fi

echo ""
echo "========================================="
echo "Ready to deploy. Review the plan above."
echo "========================================="
echo ""
read -p "Do you want to apply this plan? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled."
    exit 0
fi

# Step 5: Apply Terraform
echo ""
echo "Step 5: Applying Terraform configuration..."
terraform apply tfplan

if [ $? -ne 0 ]; then
    echo "❌ Terraform apply failed"
    exit 1
fi

echo ""
echo "✅ Infrastructure deployed successfully!"
echo ""

# Step 6: Get API Gateway URL
echo "Step 6: Retrieving deployment information..."
API_URL=$(terraform output -raw api_gateway_url 2>/dev/null || echo "N/A")
HEALTH_URL=$(terraform output -raw api_health_check_url 2>/dev/null || echo "N/A")
DOCS_URL=$(terraform output -raw api_docs_url 2>/dev/null || echo "N/A")
FUNCTION_NAME=$(terraform output -raw lambda_api_function_name 2>/dev/null || echo "N/A")

echo ""
echo "========================================="
echo "Deployment Summary - STAGING"
echo "========================================="
echo "Lambda Function: $FUNCTION_NAME"
echo "API Gateway URL: $API_URL"
echo "Health Check URL: $HEALTH_URL"
echo "API Docs URL: $DOCS_URL"
echo ""

# Step 7: Verify deployment
echo "Step 7: Verifying deployment..."
echo "Waiting 10 seconds for API Gateway to propagate..."
sleep 10

if [ "$HEALTH_URL" != "N/A" ]; then
    echo "Testing health endpoint: $HEALTH_URL"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || echo "000")
    
    if [ "$HTTP_CODE" == "200" ]; then
        echo "✅ Health check passed (HTTP $HTTP_CODE)"
        echo ""
        echo "Health response:"
        curl -s "$HEALTH_URL" | python3 -m json.tool 2>/dev/null || curl -s "$HEALTH_URL"
    elif [ "$HTTP_CODE" == "000" ]; then
        echo "⚠️  Could not reach health endpoint (may still be propagating)"
        echo "   Try again in a few moments: curl $HEALTH_URL"
    else
        echo "⚠️  Health check returned HTTP $HTTP_CODE (may still be propagating)"
        echo "   Try again in a few moments: curl $HEALTH_URL"
    fi
else
    echo "⚠️  Could not retrieve health URL"
fi

echo ""
echo "========================================="
echo "✅ Staging Deployment Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Test the API: curl $HEALTH_URL"
echo "  2. View docs: $DOCS_URL"
echo "  3. Monitor logs: aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
echo ""
