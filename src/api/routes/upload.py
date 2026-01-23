"""Upload endpoint for video processing.

DEPRECATED: This endpoint is deprecated in favor of presigned S3 URL uploads.
Use /api/v1/upload/presigned-url and /api/v1/upload/confirm instead.

The multipart form data upload has known corruption issues in Lambda environments
due to FastAPI/Mangum multipart parsing limitations. Presigned URLs bypass this
entirely by uploading directly to S3.
"""

import logging
from fastapi import APIRouter, HTTPException, status

from src.api.models.responses import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", deprecated=True)
async def upload_video():
    """DEPRECATED: Use presigned S3 URL uploads instead.
    
    This endpoint is deprecated due to multipart form data corruption issues
    in Lambda environments. Use the following flow instead:
    
    1. POST /api/v1/upload/presigned-url - Get presigned URL
    2. PUT <presigned_url> - Upload file directly to S3
    3. POST /api/v1/upload/confirm - Confirm upload and create job
    
    Returns:
        ErrorResponse directing users to use presigned URLs
    """
    logger.warning("Deprecated multipart upload endpoint called - redirecting to presigned URL flow")
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "error": "This endpoint is deprecated",
            "message": "Use presigned S3 URL uploads instead",
            "endpoints": {
                "get_presigned_url": "POST /api/v1/upload/presigned-url",
                "upload_file": "PUT <presigned_url>",
                "confirm_upload": "POST /api/v1/upload/confirm"
            },
            "documentation": "See /docs for API documentation"
        }
    )


__all__ = ["router"]
