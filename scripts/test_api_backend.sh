#!/bin/bash
# Comprehensive backend testing script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"
source venv/bin/activate

echo "========================================="
echo "Backend Testing & Verification"
echo "========================================="
echo ""

# 1. Build Lambda package
echo "Step 1: Building Lambda API package..."
./scripts/build_lambda_api_package.sh
echo ""

# 2. Run unit tests
echo "Step 2: Running unit tests..."
pytest tests/unit/test_api_routes.py tests/unit/test_lambda_api_handler.py -v --tb=short
echo ""

# 3. Run integration tests
echo "Step 3: Running integration tests..."
pytest tests/integration/test_api_end_to_end.py tests/integration/test_api_robustness.py -v --tb=short
echo ""

# 4. Verify Lambda package
echo "Step 4: Verifying Lambda package..."
if [ -f "infrastructure/lambda_api_package.zip" ]; then
    SIZE=$(du -h infrastructure/lambda_api_package.zip | cut -f1)
    echo "✅ Lambda package exists: $SIZE"
    
    # Check package contents
    unzip -l infrastructure/lambda_api_package.zip | head -20
    echo ""
else
    echo "❌ Lambda package not found"
    exit 1
fi

# 5. Validate Terraform
echo "Step 5: Validating Terraform configuration..."
cd infrastructure
terraform validate
echo "✅ Terraform validation passed"
echo ""

# 6. Test API locally (quick test)
echo "Step 6: Testing API locally..."
cd "$PROJECT_ROOT"
timeout 10 python run_api.py --host 127.0.0.1 --port 8001 &
API_PID=$!
sleep 3

# Test endpoints
curl -s http://127.0.0.1:8001/health | grep -q "healthy" && echo "✅ Health endpoint works" || echo "❌ Health endpoint failed"
curl -s http://127.0.0.1:8001/ | grep -q "LifeStream" && echo "✅ Root endpoint works" || echo "❌ Root endpoint failed"

kill $API_PID 2>/dev/null || true
echo ""

echo "========================================="
echo "✅ Backend Testing Complete"
echo "========================================="
