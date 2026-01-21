"""Lambda handler for FastAPI application.

This handler wraps the FastAPI app using Mangum to enable it to run on AWS Lambda
with API Gateway.
"""

import logging
from mangum import Mangum
from src.api.main import app

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create ASGI adapter for Lambda
handler = Mangum(app, lifespan="off")  # Lifespan handled by Lambda

def lambda_handler(event, context):
    """Lambda handler entry point for API Gateway."""
    return handler(event, context)

__all__ = ["lambda_handler", "handler"]
