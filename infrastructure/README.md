# Infrastructure as Code

This directory contains Terraform configurations for provisioning AWS resources for LifeStream.

## Prerequisites

1. **AWS Account** with admin access
2. **AWS CLI** installed and configured
3. **Terraform** installed (see installation below)

## Installation

### Install Terraform

**macOS (using Homebrew):**
```bash
brew install terraform
```

**Or download manually:**
1. Visit https://www.terraform.io/downloads
2. Download for macOS
3. Extract and add to PATH

**Verify installation:**
```bash
terraform version
```

### Configure AWS Credentials

**Option 1: Using AWS CLI (Recommended)**
```bash
aws configure
```
Enter:
- AWS Access Key ID: [your access key]
- AWS Secret Access Key: [your secret key]
- Default region: us-east-1 (or your preferred region)
- Default output format: json

**Option 2: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

**Option 3: Credentials File**
Create `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = your_access_key
aws_secret_access_key = your_secret_key
```

Create `~/.aws/config`:
```ini
[default]
region = us-east-1
output = json
```

## Usage

### Initialize Terraform
```bash
cd infrastructure
terraform init
```

### Plan Changes
```bash
terraform plan
```

### Apply Changes
```bash
terraform apply
```

### Destroy Resources
```bash
terraform destroy
```

## Structure

- `main.tf` - Main infrastructure configuration
- `variables.tf` - Input variables
- `outputs.tf` - Output values
- `terraform.tfvars` - Variable values (create from terraform.tfvars.example)
- `.terraform/` - Terraform state (gitignored)

## Important Notes

- **Never commit** `terraform.tfvars` or `.terraform/` to git
- Store Terraform state in S3 backend for team collaboration (see `backend.tf`)
- Use different workspaces for dev/staging/prod environments
