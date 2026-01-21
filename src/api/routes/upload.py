"""Upload endpoint for video processing."""

import logging
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse

from config.settings import Settings
from src.services.video_service import VideoService
from src.api.models.responses import UploadResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Allowed video file types
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB


@router.post("/upload", response_model=UploadResponse)
async def upload_video(
    file: UploadFile = File(..., description="Video file to upload"),
    metadata: Optional[str] = Form(None, description="Optional JSON metadata"),
):
    """Upload a video file for processing.
    
    This endpoint:
    1. Validates the uploaded file (type and size)
    2. Uploads the file to S3
    3. Creates a processing job and enqueues it
    4. Returns job ID and status
    
    Args:
        file: Uploaded video file
        metadata: Optional JSON string with metadata
        
    Returns:
        UploadResponse with job_id and status
        
    Raises:
        HTTPException: If file validation fails
    """
    logger.info(f"Received upload request: {file.filename}")
    
    # Validate file type
    file_ext = None
    if file.filename:
        file_ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    
    if not file_ext or file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file to get size
    try:
        content = await file.read()
        file_size = len(content)
        
        # Validate file size
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024**3):.1f} GB"
            )
        
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
        # Parse metadata if provided
        import json
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON in metadata field"
                )
        
        # Save file temporarily
        import tempfile
        import os
        from pathlib import Path
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(content)
        
        try:
            # Initialize services
            settings = Settings()
            video_service = VideoService(settings)
            
            # Create upload job (uploads to S3 and enqueues)
            job = video_service.create_upload_job(
                video_file_path=tmp_path,
                metadata=metadata_dict
            )
            
            # Estimate completion time (rough estimate: 1 minute per 10 minutes of video)
            # This is a placeholder - real estimation would require video duration
            estimated_completion = datetime.utcnow() + timedelta(minutes=30)
            
            logger.info(f"Upload job created: {job.job_id}")
            
            return UploadResponse(
                job_id=job.job_id,
                status="queued",
                video_url=f"s3://{job.video_s3_bucket}/{job.video_s3_key}",
                estimated_completion=estimated_completion,
                message="Video uploaded successfully and processing queued"
            )
        
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


__all__ = ["router"]
