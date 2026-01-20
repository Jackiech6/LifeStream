#!/bin/bash
# Build Lambda deployment package for video processing function

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"
PACKAGE_DIR="/tmp/lambda_package_$$"
PACKAGE_ZIP="$INFRA_DIR/lambda_package.zip"

echo "Building Lambda deployment package..."
echo "Project root: $PROJECT_ROOT"
echo "Package directory: $PACKAGE_DIR"

# Create temporary package directory
mkdir -p "$PACKAGE_DIR"

# Copy source code
echo "Copying source code..."
cp -r "$PROJECT_ROOT/src" "$PACKAGE_DIR/"
cp -r "$PROJECT_ROOT/config" "$PACKAGE_DIR/"

# Create lambda_handler.py in root of package
echo "Creating lambda_handler.py..."
cat > "$PACKAGE_DIR/lambda_handler.py" << 'EOF'
"""Lambda entry point - redirects to workers.lambda_handler."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.workers.lambda_handler import lambda_handler

# Export for Lambda
__all__ = ["lambda_handler"]
EOF

# Install dependencies
echo "Installing dependencies..."
cd "$PACKAGE_DIR"
python3 -m pip install -r "$PROJECT_ROOT/requirements.txt" -t . --no-deps --quiet 2>/dev/null || {
    echo "Warning: pip install failed, trying with --system..."
    python3 -m pip install -r "$PROJECT_ROOT/requirements.txt" -t . --system --quiet 2>/dev/null || true
}

# Remove unnecessary files
echo "Cleaning up..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true

# Create zip file
echo "Creating zip package..."
cd "$PACKAGE_DIR"
zip -r "$PACKAGE_ZIP" . -q

# Cleanup
rm -rf "$PACKAGE_DIR"

echo "✅ Lambda package created: $PACKAGE_ZIP"
echo "   Size: $(du -h "$PACKAGE_ZIP" | cut -f1)"
echo ""
echo "Next steps:"
echo "  1. Review the package: unzip -l $PACKAGE_ZIP"
echo "  2. Deploy with Terraform: cd infrastructure && terraform apply"
