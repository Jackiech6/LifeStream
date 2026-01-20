#!/bin/bash
# Verify AWS Setup Script
# This script verifies that AWS is properly configured

set -e

echo "=== LifeStream AWS Setup Verification ==="
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed"
    exit 1
fi
echo "✅ AWS CLI is installed: $(aws --version)"

# Check credentials
echo ""
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials are not configured"
    echo "   Run: ./scripts/setup_aws_credentials.sh"
    exit 1
fi

echo "✅ AWS credentials are configured"
echo ""
echo "Current AWS identity:"
aws sts get-caller-identity | jq '.' 2>/dev/null || aws sts get-caller-identity

# Check region
echo ""
echo "Checking AWS region..."
REGION=$(aws configure get region)
if [[ -z "$REGION" ]]; then
    echo "⚠️  Default region is not set"
    echo "   Set it with: aws configure set region us-east-1"
else
    echo "✅ Default region: $REGION"
fi

# Check Terraform
echo ""
if ! command -v terraform &> /dev/null; then
    echo "⚠️  Terraform is not installed"
    echo "   Install with: brew install terraform"
else
    echo "✅ Terraform is installed: $(terraform version | head -1)"
fi

# Check if infrastructure directory exists
echo ""
if [[ -d "infrastructure" ]]; then
    echo "✅ Infrastructure directory exists"
    
    if [[ -f "infrastructure/terraform.tfvars" ]]; then
        echo "✅ terraform.tfvars exists"
    else
        echo "⚠️  terraform.tfvars not found"
        echo "   Copy infrastructure/terraform.tfvars.example to infrastructure/terraform.tfvars"
    fi
else
    echo "❌ Infrastructure directory not found"
fi

echo ""
echo "=== Verification Complete ==="
echo ""
echo "Next steps:"
echo "  1. If Terraform is not installed: brew install terraform"
echo "  2. Configure terraform.tfvars: cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars"
echo "  3. Edit infrastructure/terraform.tfvars with your values"
echo "  4. Initialize Terraform: cd infrastructure && terraform init"
echo "  5. Plan infrastructure: terraform plan"
echo "  6. Apply infrastructure: terraform apply"
