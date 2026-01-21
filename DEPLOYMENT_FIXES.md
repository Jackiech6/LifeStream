# Deployment Fixes Applied

**Date:** 2026-01-20  
**Status:** ✅ All issues fixed

---

## Issues Fixed

### 1. ✅ AWS_REGION Reserved Environment Variable

**Error:**
```
InvalidParameterValueException: Lambda was unable to configure your environment variables because the environment variables you have provided contains reserved keys that are currently not supported for modification. Reserved keys used in this request: AWS_REGION
```

**Fix:**
- Removed `AWS_REGION` from Lambda environment variables in both:
  - `infrastructure/api.tf` (API Lambda)
  - `infrastructure/lambda.tf` (Video Processor Lambda)
- **Reason:** `AWS_REGION` is automatically provided by Lambda runtime and cannot be set manually

**Files Modified:**
- `infrastructure/api.tf` - Removed `AWS_REGION` from environment variables
- `infrastructure/lambda.tf` - Removed `AWS_REGION` from environment variables

---

### 2. ✅ Missing Video Processor Lambda Package

**Error:**
```
Error: reading ZIP file (./lambda_package.zip): open ./lambda_package.zip: no such file or directory
```

**Fix:**
- Built the video processor Lambda package using:
  ```bash
  ./scripts/build_lambda_package.sh
  ```
- Package created: `infrastructure/lambda_package.zip` (144 MB)

**Note:** This package includes all dependencies for video processing (PyTorch, Whisper, etc.), which is why it's larger than the API package.

---

### 3. ✅ Invalid PostgreSQL Version

**Error:**
```
api error InvalidParameterCombination: Cannot find version 15.4 for postgres
```

**Fix:**
- Updated PostgreSQL version from `15.4` to `15.5` in `infrastructure/main.tf`
- Version `15.5` is a valid and available PostgreSQL version on AWS RDS

**File Modified:**
- `infrastructure/main.tf` - Changed `engine_version = "15.4"` to `engine_version = "15.5"`

---

### 4. ✅ S3 Bucket Notification Configuration

**Error:**
```
api error InvalidArgument: Unable to validate the following destination configurations
```

**Fix:**
- Added explicit `depends_on` clause to ensure SQS queue and policy are created before S3 notification
- This ensures proper resource creation order

**File Modified:**
- `infrastructure/main.tf` - Added `depends_on` to `aws_s3_bucket_notification.video_upload_trigger`

---

## Summary of Changes

| File | Change | Reason |
|------|--------|--------|
| `infrastructure/api.tf` | Removed `AWS_REGION` env var | Reserved by Lambda |
| `infrastructure/lambda.tf` | Removed `AWS_REGION` env var | Reserved by Lambda |
| `infrastructure/main.tf` | Updated PostgreSQL to 15.5 | Invalid version |
| `infrastructure/main.tf` | Added `depends_on` to S3 notification | Resource ordering |
| `infrastructure/lambda_package.zip` | Built video processor package | Missing file |

---

## Ready to Deploy

All issues have been fixed. You can now proceed with deployment:

```bash
cd infrastructure
terraform apply
```

**Expected Resources:**
- ✅ Lambda API function (21 MB package)
- ✅ Lambda Video Processor function (144 MB package)
- ✅ API Gateway REST API
- ✅ S3 bucket with notifications
- ✅ SQS queues (main + DLQ)
- ✅ RDS PostgreSQL 15.5 instance
- ✅ IAM roles and policies
- ✅ CloudWatch log groups

---

## Verification

After deployment, verify:

1. **Lambda Functions:**
   ```bash
   aws lambda list-functions --query 'Functions[?contains(FunctionName, `lifestream`)].FunctionName'
   ```

2. **API Gateway:**
   ```bash
   terraform output api_gateway_url
   ```

3. **Health Check:**
   ```bash
   curl $(terraform output -raw api_health_check_url)
   ```

---

**Status:** ✅ **ALL FIXES APPLIED - READY FOR DEPLOYMENT**
