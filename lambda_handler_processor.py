"""Lambda entry point for video processor - container image version."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.workers.lambda_handler import lambda_handler

# Export for Lambda container image
# Lambda will call lambda_function.lambda_handler
__all__ = ["lambda_handler"]
