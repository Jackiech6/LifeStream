# Sub-Stage 3.1.1: Cloud Provider Account Setup - Completion Guide

This document provides step-by-step instructions to complete the AWS account setup for LifeStream.

## ✅ Completed Steps

You have already:
- ✅ Set up AWS CLI locally
- ✅ Configured an admin user

## 📋 Remaining Tasks

### 1. Verify AWS CLI Configuration

Run the verification script:
```bash
./scripts/verify_aws_setup.sh
```

Or manually verify:
```bash
aws sts get-caller-identity
```

If credentials are not configured, run:
```bash
./scripts/setup_aws_credentials.sh
```

### 2. Set Up Billing Alerts

**Option A: Using Script (Recommended)**
```bash
./scripts/setup_billing_alerts.sh
```

**Option B: Manual Setup via AWS Console**
1. Go to AWS Console → CloudWatch → Alarms
2. Create alarm → Select "Billing" metric
3. Set threshold (e.g., $50)
4. Create SNS topic and subscribe your email
5. Confirm email subscription

**Option C: Using Terraform (After infrastructure setup)**
The Terraform configuration includes billing alerts. Set `enable_billing_alerts = true` and `notification_email` in `terraform.tfvars`.

### 3. Install Terraform

**macOS (Homebrew):**
```bash
brew install terraform
```

**Verify installation:**
```bash
terraform version
```

### 4. Configure Terraform Variables

1. Copy the example file:
```bash
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
```

2. Edit `terraform.tfvars` with your values:
```hcl
aws_region = "us-east-1"
project_name = "lifestream"
environment = "dev"

# Database password - USE A STRONG PASSWORD!
db_password = "YourStrongPassword123!"

# Email for billing alerts
notification_email = "your-email@example.com"
billing_alert_threshold = 50.0
```

**⚠️ Important:** Never commit `terraform.tfvars` to git (it's in .gitignore)

### 5. Initialize Terraform

```bash
cd infrastructure
terraform init
```

This will:
- Download AWS provider
- Initialize backend (local state by default)

### 6. Validate Terraform Configuration

```bash
terraform validate
```

This checks syntax and configuration.

### 7. Plan Infrastructure

Preview what will be created:
```bash
terraform plan
```

Review the output carefully. It should show:
- S3 bucket for videos
- SQS queue for processing
- RDS database
- IAM roles
- Security groups
- Billing alarms (if enabled)

### 8. Apply Infrastructure (Optional - Do this when ready)

**⚠️ Warning:** This will create AWS resources and incur costs!

```bash
terraform apply
```

Type `yes` when prompted. This will:
- Create all AWS resources
- Take 10-15 minutes (mostly RDS creation)
- Output resource information

### 9. Verify Infrastructure

After applying, verify resources:

```bash
# Check S3 bucket
aws s3 ls | grep lifestream

# Check SQS queue
aws sqs list-queues

# Check RDS instance
aws rds describe-db-instances --query 'DBInstances[?DBInstanceIdentifier==`lifestream-db-dev`]'

# Check billing alarm
aws cloudwatch describe-alarms --alarm-names lifestream-billing-alert-dev
```

## 🧪 Testing

### Unit Test: Terraform Validation

```bash
cd infrastructure
terraform validate
terraform fmt -check  # Check formatting
```

### Integration Test: Dry Run

```bash
terraform plan -detailed-exitcode
```

Exit code 0 = no changes, 1 = error, 2 = changes planned

### Compliance Test: IAM Roles

Review IAM policies created by Terraform:
```bash
terraform show | grep -A 20 "aws_iam_role_policy"
```

Verify:
- ✅ Least privilege principle (only necessary permissions)
- ✅ No wildcard permissions for sensitive operations
- ✅ Resource-specific ARNs (not `*`)

## 📝 Configuration Files Created

- `infrastructure/main.tf` - Main infrastructure configuration
- `infrastructure/variables.tf` - Input variables
- `infrastructure/outputs.tf` - Output values
- `infrastructure/terraform.tfvars.example` - Example configuration
- `infrastructure/.gitignore` - Git ignore rules
- `scripts/setup_aws_credentials.sh` - Credentials setup script
- `scripts/setup_billing_alerts.sh` - Billing alerts script
- `scripts/verify_aws_setup.sh` - Verification script

## 🔐 Security Best Practices

1. **Never commit credentials:**
   - `terraform.tfvars` is gitignored
   - `.aws/credentials` should never be committed
   - Use environment variables or AWS IAM roles in production

2. **Use least privilege:**
   - IAM roles created by Terraform follow least privilege
   - Review and restrict permissions as needed

3. **Enable MFA:**
   - Enable MFA on your AWS account
   - Use MFA for sensitive operations

4. **Monitor costs:**
   - Billing alerts are configured
   - Review AWS Cost Explorer regularly

## 🚨 Troubleshooting

### "Unable to locate credentials"
```bash
# Run credentials setup
./scripts/setup_aws_credentials.sh

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

### "Terraform not found"
```bash
brew install terraform
```

### "Region not set"
```bash
aws configure set region us-east-1
```

### "Billing alarm not working"
- Check email subscription is confirmed
- Verify alarm is in "OK" or "ALARM" state (not "INSUFFICIENT_DATA")
- Wait 24 hours for first evaluation

## ✅ Completion Checklist

- [ ] AWS CLI configured and verified
- [ ] Terraform installed
- [ ] `terraform.tfvars` created and configured
- [ ] Terraform initialized (`terraform init`)
- [ ] Terraform validated (`terraform validate`)
- [ ] Infrastructure planned (`terraform plan`)
- [ ] Billing alerts configured (optional but recommended)
- [ ] All scripts are executable

## 🎯 Next Steps

Once this sub-stage is complete, proceed to:
- **Sub-Stage 3.1.2:** Object Storage Setup (S3 configuration)
- **Sub-Stage 3.1.3:** Vector Database Migration (Pinecone setup)

---

**Status:** Ready for implementation  
**Last Updated:** 2026-01-20
