#!/bin/bash
# Setup AWS Credentials Script
# This script helps configure AWS CLI credentials

set -e

echo "=== LifeStream AWS Credentials Setup ==="
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed."
    echo "Install it with: brew install awscli"
    exit 1
fi

echo "✅ AWS CLI is installed"
echo ""

# Check if credentials already exist
if aws sts get-caller-identity &> /dev/null; then
    echo "✅ AWS credentials are already configured"
    echo ""
    echo "Current identity:"
    aws sts get-caller-identity
    echo ""
    read -p "Do you want to reconfigure? (y/N): " reconfigure
    if [[ ! $reconfigure =~ ^[Yy]$ ]]; then
        echo "Keeping existing configuration."
        exit 0
    fi
fi

echo "To configure AWS credentials, you need:"
echo "  1. AWS Access Key ID"
echo "  2. AWS Secret Access Key"
echo "  3. Default region (e.g., us-east-1)"
echo ""

read -p "Do you have these credentials ready? (y/N): " ready
if [[ ! $ready =~ ^[Yy]$ ]]; then
    echo ""
    echo "To get AWS credentials:"
    echo "  1. Log in to AWS Console: https://console.aws.amazon.com"
    echo "  2. Go to IAM → Users → Your User → Security Credentials"
    echo "  3. Create Access Key"
    echo "  4. Download or copy the credentials"
    echo ""
    exit 0
fi

echo ""
echo "Running 'aws configure'..."
echo "You will be prompted for:"
echo "  - AWS Access Key ID"
echo "  - AWS Secret Access Key"
echo "  - Default region (recommended: us-east-1)"
echo "  - Default output format (recommended: json)"
echo ""

aws configure

echo ""
echo "Verifying configuration..."
if aws sts get-caller-identity &> /dev/null; then
    echo "✅ AWS credentials configured successfully!"
    echo ""
    echo "Your AWS identity:"
    aws sts get-caller-identity
else
    echo "❌ Configuration failed. Please check your credentials."
    exit 1
fi
