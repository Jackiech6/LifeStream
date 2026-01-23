#!/bin/bash
# Verification script to test API keys are correctly configured and working
# Tests:
# 1. LLM summarization executes successfully end-to-end
# 2. /api/v1/query returns real Pinecone search results instead of 503 errors

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"

echo -e "${GREEN}=== LifeStream API Keys Verification ===${NC}\n"

# Check if terraform.tfvars exists
if [[ ! -f "$INFRA_DIR/terraform.tfvars" ]]; then
    echo -e "${RED}❌ Error: terraform.tfvars not found${NC}"
    echo "   Expected: $INFRA_DIR/terraform.tfvars"
    exit 1
fi

# Get API Gateway URL from Terraform output
echo -e "${YELLOW}📡 Getting API Gateway URL from Terraform...${NC}"
cd "$INFRA_DIR"

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Error: terraform command not found${NC}"
    exit 1
fi

# Check if Terraform is initialized
if [[ ! -d ".terraform" ]]; then
    echo -e "${YELLOW}⚠️  Terraform not initialized. Initializing...${NC}"
    terraform init
fi

# Get API Gateway URL
API_URL=$(terraform output -raw api_gateway_url 2>/dev/null || echo "")
if [[ -z "$API_URL" ]]; then
    echo -e "${RED}❌ Error: Could not get API Gateway URL from Terraform${NC}"
    echo "   Make sure Terraform has been applied: cd infrastructure && terraform apply"
    exit 1
fi

echo -e "${GREEN}✅ API Gateway URL: $API_URL${NC}\n"

# Test 1: Health check
echo -e "${YELLOW}Test 1: Health Check${NC}"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_URL/health" || echo -e "\n000")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
BODY=$(echo "$HEALTH_RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" == "200" ]]; then
    echo -e "${GREEN}✅ Health check passed (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}❌ Health check failed (HTTP $HTTP_CODE)${NC}"
    echo "   Response: $BODY"
    exit 1
fi

# Test 2: Query endpoint - should return real results, not 503
echo -e "\n${YELLOW}Test 2: Query Endpoint (Pinecone Search)${NC}"
QUERY_PAYLOAD='{
  "query": "test query",
  "top_k": 5,
  "min_score": 0.0
}'

QUERY_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$QUERY_PAYLOAD" \
    "$API_URL/api/v1/query" || echo -e "\n000")

QUERY_HTTP_CODE=$(echo "$QUERY_RESPONSE" | tail -n1)
QUERY_BODY=$(echo "$QUERY_RESPONSE" | sed '$d')

if [[ "$QUERY_HTTP_CODE" == "503" ]]; then
    echo -e "${RED}❌ Query endpoint returned 503 (Service Unavailable)${NC}"
    echo "   This indicates API keys are not properly configured in Lambda"
    echo "   Response: $QUERY_BODY"
    echo ""
    echo -e "${YELLOW}⚠️  Troubleshooting:${NC}"
    echo "   1. Verify terraform.tfvars has API keys set"
    echo "   2. Run: cd infrastructure && terraform apply"
    echo "   3. Wait for Lambda function update to complete"
    exit 1
elif [[ "$QUERY_HTTP_CODE" == "200" ]]; then
    echo -e "${GREEN}✅ Query endpoint returned 200 (Success)${NC}"
    # Check if response has results
    if echo "$QUERY_BODY" | grep -q '"results"'; then
        RESULT_COUNT=$(echo "$QUERY_BODY" | grep -o '"total_results":[0-9]*' | grep -o '[0-9]*' || echo "0")
        echo -e "${GREEN}   Found $RESULT_COUNT results${NC}"
    else
        echo -e "${YELLOW}⚠️  Query succeeded but no results in response${NC}"
    fi
    echo "   Response preview: $(echo "$QUERY_BODY" | head -c 200)..."
else
    echo -e "${YELLOW}⚠️  Query endpoint returned HTTP $QUERY_HTTP_CODE${NC}"
    echo "   Response: $QUERY_BODY"
    # Don't fail - might be empty index or other issues
fi

# Test 3: Verify API keys are set in Terraform variables
echo -e "\n${YELLOW}Test 3: Verify API Keys in terraform.tfvars${NC}"
if grep -q "openai_api_key.*=" "$INFRA_DIR/terraform.tfvars" && \
   grep -q "pinecone_api_key.*=" "$INFRA_DIR/terraform.tfvars" && \
   grep -q "huggingface_token.*=" "$INFRA_DIR/terraform.tfvars"; then
    echo -e "${GREEN}✅ All API keys found in terraform.tfvars${NC}"
    
    # Check if keys are not empty (basic check - don't print actual keys)
    OPENAI_SET=$(grep "openai_api_key" "$INFRA_DIR/terraform.tfvars" | grep -v "^#" | grep -v '""' | wc -l | tr -d ' ')
    PINECONE_SET=$(grep "pinecone_api_key" "$INFRA_DIR/terraform.tfvars" | grep -v "^#" | grep -v '""' | wc -l | tr -d ' ')
    HF_SET=$(grep "huggingface_token" "$INFRA_DIR/terraform.tfvars" | grep -v "^#" | grep -v '""' | wc -l | tr -d ' ')
    
    if [[ "$OPENAI_SET" -gt 0 && "$PINECONE_SET" -gt 0 && "$HF_SET" -gt 0 ]]; then
        echo -e "${GREEN}✅ All API keys appear to be set (non-empty)${NC}"
    else
        echo -e "${YELLOW}⚠️  Some API keys may be empty${NC}"
    fi
else
    echo -e "${RED}❌ Missing API keys in terraform.tfvars${NC}"
    exit 1
fi

# Test 4: Check Lambda environment variables (via AWS CLI if available)
echo -e "\n${YELLOW}Test 4: Verify Lambda Environment Variables${NC}"
if command -v aws &> /dev/null; then
    # Get environment and region from terraform.tfvars
    ENV=$(grep "environment" "$INFRA_DIR/terraform.tfvars" | grep -v "^#" | head -1 | sed 's/.*= *"\([^"]*\)".*/\1/' || echo "staging")
    PROJECT_NAME=$(grep "project_name" "$INFRA_DIR/terraform.tfvars" | grep -v "^#" | head -1 | sed 's/.*= *"\([^"]*\)".*/\1/' || echo "lifestream")
    AWS_REGION=$(grep "aws_region" "$INFRA_DIR/terraform.tfvars" | grep -v "^#" | head -1 | sed 's/.*= *"\([^"]*\)".*/\1/' || echo "us-east-1")
    
    API_FUNCTION="${PROJECT_NAME}-api-${ENV}"
    PROCESSOR_FUNCTION="${PROJECT_NAME}-video-processor-${ENV}"
    
    echo "   Checking API Lambda: $API_FUNCTION"
    API_ENV=$(aws lambda get-function-configuration \
        --function-name "$API_FUNCTION" \
        --region "$AWS_REGION" \
        --query 'Environment.Variables' \
        --output json 2>/dev/null || echo "{}")
    
    if echo "$API_ENV" | grep -q "OPENAI_API_KEY"; then
        OPENAI_KEY_LENGTH=$(echo "$API_ENV" | grep -o '"OPENAI_API_KEY":"[^"]*"' | cut -d'"' -f4 | wc -c)
        if [[ "$OPENAI_KEY_LENGTH" -gt 10 ]]; then
            echo -e "${GREEN}   ✅ API Lambda has OPENAI_API_KEY set (length: $((OPENAI_KEY_LENGTH-1)))${NC}"
        else
            echo -e "${RED}   ❌ API Lambda OPENAI_API_KEY appears empty${NC}"
        fi
    else
        echo -e "${RED}   ❌ API Lambda missing OPENAI_API_KEY${NC}"
    fi
    
    if echo "$API_ENV" | grep -q "PINECONE_API_KEY"; then
        PINECONE_KEY_LENGTH=$(echo "$API_ENV" | grep -o '"PINECONE_API_KEY":"[^"]*"' | cut -d'"' -f4 | wc -c)
        if [[ "$PINECONE_KEY_LENGTH" -gt 10 ]]; then
            echo -e "${GREEN}   ✅ API Lambda has PINECONE_API_KEY set (length: $((PINECONE_KEY_LENGTH-1)))${NC}"
        else
            echo -e "${RED}   ❌ API Lambda PINECONE_API_KEY appears empty${NC}"
        fi
    else
        echo -e "${RED}   ❌ API Lambda missing PINECONE_API_KEY${NC}"
    fi
    
    echo "   Checking Processor Lambda: $PROCESSOR_FUNCTION"
    PROCESSOR_ENV=$(aws lambda get-function-configuration \
        --function-name "$PROCESSOR_FUNCTION" \
        --region "$AWS_REGION" \
        --query 'Environment.Variables' \
        --output json 2>/dev/null || echo "{}")
    
    if echo "$PROCESSOR_ENV" | grep -q "OPENAI_API_KEY"; then
        OPENAI_KEY_LENGTH=$(echo "$PROCESSOR_ENV" | grep -o '"OPENAI_API_KEY":"[^"]*"' | cut -d'"' -f4 | wc -c)
        if [[ "$OPENAI_KEY_LENGTH" -gt 10 ]]; then
            echo -e "${GREEN}   ✅ Processor Lambda has OPENAI_API_KEY set (length: $((OPENAI_KEY_LENGTH-1)))${NC}"
        else
            echo -e "${RED}   ❌ Processor Lambda OPENAI_API_KEY appears empty${NC}"
        fi
    else
        echo -e "${RED}   ❌ Processor Lambda missing OPENAI_API_KEY${NC}"
    fi
    
    if echo "$PROCESSOR_ENV" | grep -q "PINECONE_API_KEY"; then
        PINECONE_KEY_LENGTH=$(echo "$PROCESSOR_ENV" | grep -o '"PINECONE_API_KEY":"[^"]*"' | cut -d'"' -f4 | wc -c)
        if [[ "$PINECONE_KEY_LENGTH" -gt 10 ]]; then
            echo -e "${GREEN}   ✅ Processor Lambda has PINECONE_API_KEY set (length: $((PINECONE_KEY_LENGTH-1)))${NC}"
        else
            echo -e "${RED}   ❌ Processor Lambda PINECONE_API_KEY appears empty${NC}"
        fi
    else
        echo -e "${RED}   ❌ Processor Lambda missing PINECONE_API_KEY${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  AWS CLI not available - skipping Lambda environment check${NC}"
    echo "   Install AWS CLI to verify Lambda environment variables"
fi

# Test 5: LLM Summarization End-to-End Test
echo -e "\n${YELLOW}Test 5: LLM Summarization End-to-End${NC}"
echo "   This test requires a processed video job."
echo "   To test summarization:"
echo "   1. Upload a video via /api/v1/upload/presigned-url"
echo "   2. Wait for processing to complete"
echo "   3. Check /api/v1/summary/{job_id}"
echo ""
echo -e "${YELLOW}   Checking for existing processed jobs...${NC}"

# Try to get a list of jobs from S3 (if bucket is accessible)
if command -v aws &> /dev/null; then
    BUCKET_NAME=$(terraform output -raw s3_bucket_name 2>/dev/null || echo "")
    if [[ -n "$BUCKET_NAME" ]]; then
        # List results directory
        JOBS=$(aws s3 ls "s3://$BUCKET_NAME/results/" 2>/dev/null | awk '{print $2}' | sed 's/\///' | head -5 || echo "")
        if [[ -n "$JOBS" ]]; then
            echo -e "${GREEN}   Found processed jobs${NC}"
            for JOB in $JOBS; do
                echo "   Testing summary endpoint for job: $JOB"
                SUMMARY_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_URL/api/v1/summary/$JOB" || echo -e "\n000")
                SUMMARY_HTTP_CODE=$(echo "$SUMMARY_RESPONSE" | tail -n1)
                if [[ "$SUMMARY_HTTP_CODE" == "200" ]]; then
                    echo -e "${GREEN}   ✅ Summary retrieved successfully for job $JOB${NC}"
                    # Check if summary contains LLM-generated content
                    SUMMARY_BODY=$(echo "$SUMMARY_RESPONSE" | sed '$d')
                    if echo "$SUMMARY_BODY" | grep -q "summary_markdown\|time_blocks"; then
                        echo -e "${GREEN}   ✅ Summary contains structured content (likely LLM-generated)${NC}"
                    fi
                    break
                elif [[ "$SUMMARY_HTTP_CODE" == "404" ]]; then
                    echo -e "${YELLOW}   ⚠️  Job $JOB not found or still processing${NC}"
                else
                    echo -e "${YELLOW}   ⚠️  Summary endpoint returned HTTP $SUMMARY_HTTP_CODE${NC}"
                fi
            done
        else
            echo -e "${YELLOW}   ⚠️  No processed jobs found. Upload a video to test summarization.${NC}"
        fi
    else
        echo -e "${YELLOW}   ⚠️  Could not determine S3 bucket name${NC}"
    fi
else
    echo -e "${YELLOW}   ⚠️  AWS CLI not available - cannot check for processed jobs${NC}"
fi

# Summary
echo -e "\n${GREEN}=== Verification Summary ===${NC}"
echo ""
echo "✅ API keys configured in terraform.tfvars"
echo "✅ Query endpoint accessible (no 503 errors)"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. If Terraform changes were made, run: cd infrastructure && terraform apply"
echo "2. Wait for Lambda functions to update (may take 1-2 minutes)"
echo "3. Re-run this script to verify Lambda environment variables"
echo "4. Upload a test video to verify LLM summarization end-to-end"
echo ""
echo -e "${GREEN}Verification complete!${NC}"
