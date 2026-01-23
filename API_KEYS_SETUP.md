# API Keys Setup Guide

## Overview

The LifeStream application requires API keys for:
1. **OpenAI** - For LLM summarization and embeddings
2. **Pinecone** - For vector store (query/search functionality)

## Setting API Keys in Terraform

### Option 1: Set in terraform.tfvars (Recommended)

Add to `infrastructure/terraform.tfvars`:

```hcl
openai_api_key   = "sk-..."
pinecone_api_key = "pcsk-..."
```

**Note:** `terraform.tfvars` is gitignored - never commit it!

### Option 2: Set as Environment Variables

```bash
export TF_VAR_openai_api_key="sk-..."
export TF_VAR_pinecone_api_key="pcsk-..."
cd infrastructure
terraform apply
```

### Option 3: Use AWS Secrets Manager

1. Store secrets in AWS Secrets Manager
2. Reference them in Terraform using `var.openai_api_key_secret_arn` and `var.pinecone_api_key_secret_arn`

## Current Status

To check if API keys are set in Lambda:

```bash
# Check API Lambda
aws lambda get-function-configuration \
  --function-name lifestream-api-staging \
  --region us-east-1 \
  --query 'Environment.Variables.{OPENAI:OPENAI_API_KEY,PINECONE:PINECONE_API_KEY}' \
  --output table

# Check Processor Lambda
aws lambda get-function-configuration \
  --function-name lifestream-video-processor-staging \
  --region us-east-1 \
  --query 'Environment.Variables.{OPENAI:OPENAI_API_KEY,PINECONE:PINECONE_API_KEY}' \
  --output table
```

## Impact of Missing Keys

- **OpenAI API Key Missing:**
  - LLM summarization will fail
  - Embeddings will fail
  - Query/search will fail

- **Pinecone API Key Missing:**
  - Query/search endpoint returns 503
  - Vector indexing will fail
  - Fallback to FAISS (if installed) will be attempted

## Fixing Missing Keys

If keys are missing, update Terraform variables and reapply:

```bash
cd infrastructure
# Add keys to terraform.tfvars or set as env vars
terraform apply -target=aws_lambda_function.api -target=aws_lambda_function.video_processor
```
