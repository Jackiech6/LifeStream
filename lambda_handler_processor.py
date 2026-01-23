"""Lambda entry point for video processor - container image version."""

# Set HuggingFace cache directory to /tmp for Lambda (read-only filesystem except /tmp)
# MUST be set before importing any modules that use huggingface_hub
import os
# Set HOME to /tmp so os.path.expanduser('~') returns /tmp instead of /home/sbx_user1051
os.environ['HOME'] = '/tmp'
# Set HuggingFace-specific cache directories
os.environ['HF_HOME'] = '/tmp/huggingface'
os.environ['HF_HUB_CACHE'] = '/tmp/huggingface/hub'
# Ensure cache directory exists
os.makedirs('/tmp/huggingface/hub', exist_ok=True)

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.workers.lambda_handler import lambda_handler

# Export for Lambda container image
# Lambda will call lambda_function.lambda_handler
__all__ = ["lambda_handler"]
