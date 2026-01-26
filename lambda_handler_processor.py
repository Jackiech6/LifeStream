"""Lambda entry point for video processor - container image version."""

# MUST be set before importing any modules that use huggingface_hub / torch / etc.
import os

os.environ['HOME'] = '/tmp'
# Use baked model paths when set by Terraform (/opt/models/...); else /tmp for runtime download
if not os.environ.get('HF_HOME', '').startswith('/opt'):
    os.environ['HF_HOME'] = '/tmp/huggingface'
    os.environ['HF_HUB_CACHE'] = '/tmp/huggingface/hub'
    os.makedirs('/tmp/huggingface/hub', exist_ok=True)
if not os.environ.get('WHISPER_CACHE_DIR', '').startswith('/opt'):
    os.environ['WHISPER_CACHE_DIR'] = '/tmp/whisper_cache'
    os.makedirs('/tmp/whisper_cache', exist_ok=True)

for _k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
    os.environ.pop(_k, None)

# Cap internal threads to avoid oversubscription in Lambda (keep audio||scene parallel, limit libs)
os.environ['NUMBA_NUM_THREADS'] = '1'
os.environ['NUMBA_THREADING_LAYER'] = 'workqueue'
os.environ['NUMBA_WARNINGS'] = '0'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

os.environ['AV_LOG_LEVEL'] = '-8'

import sys
import warnings
from pathlib import Path

# Suppress numba multiprocessing lock warning (Lambda has no /dev/shm)
warnings.filterwarnings("ignore", message=".*multiprocessing lock.*")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.workers.lambda_handler import lambda_handler

# Export for Lambda container image
# Lambda will call lambda_function.lambda_handler
__all__ = ["lambda_handler"]
