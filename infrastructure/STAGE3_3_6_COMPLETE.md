# Stage 3.3.6: API Deployment - ✅ COMPLETE

**Date Completed:** 2026-01-20  
**Status:** ✅ All deployment infrastructure implemented  
**Deployment Method:** Lambda + API Gateway (consistent with video processing)

---

## ✅ Completed Components

### 1. Lambda Function ✅
- ✅ Lambda function for FastAPI application
- ✅ Mangum adapter for ASGI compatibility
- ✅ Environment variables configured
- ✅ IAM roles and policies
- ✅ CloudWatch logging

### 2. API Gateway ✅
- ✅ REST API configured
- ✅ Proxy integration with Lambda
- ✅ Stage deployment
- ✅ Automatic HTTPS endpoint

### 3. Auto-Scaling ✅
- ✅ Lambda automatically scales (built-in)
- ✅ Concurrent execution limits configurable
- ✅ No manual scaling required

### 4. CloudWatch Logging & Monitoring ✅
- ✅ CloudWatch log group for Lambda
- ✅ Function logs streaming
- ✅ Error rate alarms
- ✅ Duration alarms

### 5. Health Check ✅
- ✅ Health check endpoint (`/health`)
- ✅ Accessible via API Gateway
- ✅ Monitoring configured

---

## 📋 Implementation Details

### Lambda Handler

**Location:** `src/api/lambda_handler.py`

**Features:**
- Wraps FastAPI app with Mangum adapter
- ASGI compatibility for Lambda
- Minimal overhead
- Compatible with API Gateway

### Lambda Infrastructure

**Files Created:**
- `infrastructure/api.tf` - Complete Lambda + API Gateway deployment

**Components:**
1. **Lambda Function** - FastAPI application runtime
2. **API Gateway REST API** - HTTP endpoint
3. **API Gateway Deployment** - Stage management
4. **Lambda Permissions** - API Gateway invocation
5. **CloudWatch Logs** - Function logging
6. **Auto-Scaling** - Built-in Lambda scaling

### Auto-Scaling Configuration

**Lambda Built-in Scaling:**
- Automatic scaling based on request rate
- Concurrent executions: Unlimited (configurable)
- Reserved concurrency: Optional (for rate limiting)
- Provisioned concurrency: Optional (for consistent performance)

**Configuration:**
- Timeout: 30 seconds (API Gateway limit)
- Memory: 512 MB (adequate for API responses)
- Runtime: Python 3.11

### Monitoring & Alarms

**CloudWatch Metrics:**
- CPU utilization
- Memory utilization
- Request count
- Response time
- Error rate

**Alarms:**
- CPU > 80% for 10 minutes
- Memory > 85% for 10 minutes

**Logs:**
- Container logs: `/ecs/lifestream-api-dev`
- Retention: 7 days
- Stream prefix: `ecs`

---

## 🔧 Configuration

### Lambda Configuration

**Runtime:**
- Python 3.11
- Timeout: 30 seconds (API Gateway maximum)
- Memory: 512 MB

**Package:**
- Built via `scripts/build_lambda_api_package.sh`
- Includes API dependencies: FastAPI, Mangum, Pydantic
- **Vector Store Support:**
  - **Pinecone** - Primary vector database (default for Stage 3)
  - **FAISS** - Fallback vector store (for compatibility)
  - Both are included because `create_vector_store()` auto-selects based on config
- Includes embedding dependencies: OpenAI, NumPy
- Excludes heavy dependencies (PyTorch, Whisper, FFmpeg) not needed for API

### Environment Variables

**Required:**
- `OPENAI_API_KEY` - OpenAI API key (via Secrets Manager or env)
- `PINECONE_API_KEY` - Pinecone API key (via Secrets Manager or env)
- `AWS_S3_BUCKET_NAME` - S3 bucket name
- `AWS_SQS_QUEUE_URL` - SQS queue URL
- `AWS_REGION` - AWS region

**Optional:**
- `HUGGINGFACE_TOKEN` - For diarization models
- `PINECONE_INDEX_NAME` - Pinecone index name
- `PINECONE_ENVIRONMENT` - Pinecone region

---

## 🚀 Deployment

### Prerequisites

1. **AWS CLI configured**
2. **Docker installed**
3. **Terraform initialized**
4. **ECR repository created** (via Terraform)

### Deployment Steps

#### Option 1: Using Deployment Script

```bash
./scripts/deploy_api.sh
```

This script:
1. Builds Lambda package
2. Deploys infrastructure with Terraform
3. Updates Lambda function
4. Returns API Gateway URL

#### Option 2: Manual Deployment

```bash
# 1. Build Lambda package
./scripts/build_lambda_api_package.sh

# 2. Deploy infrastructure
cd infrastructure
terraform apply

# 3. Update Lambda function code (if needed)
aws lambda update-function-code \
    --function-name lifestream-api-dev \
    --zip-file fileb://lambda_api_package.zip
```

### Local Development with Docker

```bash
# Using Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f api

# Access API
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

---

## 📊 Infrastructure Components

### Resource Summary

| Resource | Type | Purpose |
|----------|------|---------|
| Lambda Function | Serverless Compute | Run FastAPI application |
| API Gateway REST API | HTTP Gateway | Expose API endpoints |
| API Gateway Deployment | Version Management | Deploy API versions |
| API Gateway Stage | Environment | Environment-specific config |
| Lambda Permission | Access Control | Allow API Gateway invocation |
| CloudWatch Log Group | Logging | Function logs |
| CloudWatch Alarms | Monitoring | Alert on errors/duration |

### Network Architecture

```
Internet
   ↓
API Gateway (HTTPS)
   ↓
Lambda Function (Auto-scaled)
   └── FastAPI Application
```

---

## 🔍 Monitoring & Troubleshooting

### View Logs

```bash
# Via AWS CLI
aws logs tail /aws/lambda/lifestream-api-dev --follow

# Via Console
# CloudWatch → Log groups → /aws/lambda/lifestream-api-dev
```

### Check Lambda Function Status

```bash
FUNCTION_NAME=$(terraform output -raw lambda_api_function_name)

aws lambda get-function \
    --function-name $FUNCTION_NAME

# Check function configuration
aws lambda get-function-configuration \
    --function-name $FUNCTION_NAME
```

### View Metrics

```bash
# Via CloudWatch Metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=$FUNCTION_NAME \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum
```

### Test API

```bash
# Get API Gateway URL
API_URL=$(terraform output -raw api_gateway_url)

# Health check
curl $API_URL/health

# API docs
curl $API_URL/docs

# Test endpoint
curl -X POST $API_URL/api/v1/query \
    -H "Content-Type: application/json" \
    -d '{"query": "test"}'
```

---

## 💰 Cost Estimates

### Monthly Costs (Development)

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| Lambda (1M requests) | 512 MB, 30s timeout | ~$0.20 |
| API Gateway (1M requests) | REST API | ~$3.50 |
| CloudWatch Logs | 1 GB/month | ~$0.50 |
| Data Transfer | 10 GB | ~$0.90 |
| **Total** | | **~$5-10/month** |

### Monthly Costs (Production)

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| Lambda (10M requests) | 512 MB, 30s timeout | ~$2.00 |
| API Gateway (10M requests) | REST API | ~$35.00 |
| CloudWatch Logs | 50 GB/month | ~$25 |
| Data Transfer | 100 GB | ~$9 |
| **Total** | | **~$70-80/month** |

*Note: Lambda scales automatically - pay only for requests*

*Note: Costs vary based on usage and auto-scaling activity*

---

## ⚠️ Known Limitations

1. **API Gateway Timeout:**
   - Maximum timeout: 30 seconds
   - For longer operations, consider async pattern with polling

2. **File Upload Size:**
   - API Gateway has 10 MB payload limit
   - Large video uploads should use presigned S3 URLs

3. **Cold Starts:**
   - Lambda may have cold start delays
   - Consider provisioned concurrency for production

4. **Secrets Management:**
   - Environment variables used (can be improved with Secrets Manager)
   - For production, use AWS Secrets Manager or Parameter Store

---

## ✅ Verification Checklist

- [x] Lambda handler created (Mangum adapter)
- [x] Lambda function configured
- [x] API Gateway REST API configured
- [x] API Gateway integration with Lambda
- [x] Lambda permissions configured
- [x] CloudWatch logging enabled
- [x] Health checks accessible via API Gateway
- [x] IAM roles and policies created
- [x] Deployment script created
- [x] Lambda package builder script created
- [x] Monitoring alarms configured (errors, duration)
- [x] Documentation complete

---

## 🎯 Next Steps

**Stage 3.3.6 is complete!** 

**To Deploy:**
1. Build Lambda package: `./scripts/build_lambda_api_package.sh`
2. Deploy infrastructure: `./scripts/deploy_api.sh`
3. Access API via API Gateway URL

**Future Enhancements:**
- Custom domain with Route 53
- Implement Secrets Manager for API keys
- Add WAF for security
- Configure provisioned concurrency for low latency
- Add API Gateway throttling and rate limiting

---

**Last Updated:** 2026-01-20  
**Status:** ✅ **COMPLETE**
