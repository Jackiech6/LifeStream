"""Status endpoint for job status checking."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Path

from config.settings import Settings
from src.storage.s3_service import S3Service
from src.api.models.responses import StatusResponse
from src.messaging.sqs_service import JobStatus as SQSJobStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str = Path(..., description="Job identifier")):
    """Get the status of a processing job.
    
    This endpoint checks:
    1. S3 for result files (JSON summary)
    2. Returns current status and progress
    
    Note: In a full implementation, this would query a database.
    For now, it checks S3 for result files.
    
    Args:
        job_id: Job identifier
        
    Returns:
        StatusResponse with job status and progress
        
    Raises:
        HTTPException: If job not found
    """
    logger.info(f"Status request for job: {job_id}")
    
    try:
        settings = Settings()
        s3_service = S3Service(settings)
        
        # Check for result files in S3
        result_key = f"results/{job_id}/summary.json"
        markdown_key = f"results/{job_id}/summary.md"
        
        result_exists = s3_service.file_exists(result_key)
        markdown_exists = s3_service.file_exists(markdown_key)
        
        if result_exists and markdown_exists:
            # Job completed
            status_str = "completed"
            progress = 1.0
            current_stage = "completed"
            error = None
            
            # Get file metadata for timestamps
            try:
                metadata = s3_service.get_file_metadata(result_key)
                if metadata and "uploaded_at" in metadata:
                    updated_at = datetime.fromisoformat(metadata["uploaded_at"])
                else:
                    updated_at = datetime.utcnow()
            except Exception:
                updated_at = datetime.utcnow()
        
        elif result_exists or markdown_exists:
            # Partial completion - still processing
            status_str = "processing"
            progress = 0.5
            current_stage = "processing"
            error = None
            updated_at = datetime.utcnow()
        
        else:
            # Check if job is in queue (simplified check)
            # In production, would query database
            status_str = "queued"
            progress = 0.0
            current_stage = "queued"
            error = None
            updated_at = datetime.utcnow()
        
        return StatusResponse(
            job_id=job_id,
            status=status_str,
            progress=progress,
            current_stage=current_stage,
            error=error,
            created_at=updated_at,  # Approximate
            updated_at=updated_at
        )
    
    except Exception as e:
        logger.error(f"Failed to get status for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job status: {str(e)}"
        )


__all__ = ["router"]
