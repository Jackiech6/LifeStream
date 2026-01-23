"""Presigned URL upload endpoints for direct S3 uploads.

This module provides endpoints for generating presigned S3 URLs and confirming
uploads, bypassing the multipart form data parsing issues in Lambda.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from config.settings import Settings
from src.storage.s3_service import S3Service
from src.services.video_service import VideoService
from src.api.models.responses import PresignedUrlResponse, UploadResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Allowed video file types
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB


class PresignedUrlRequest(BaseModel):
    """Request model for presigned URL generation."""
    
    filename: str = Field(..., description="Original filename (used to determine file type)")
    file_size: Optional[int] = Field(None, description="Expected file size in bytes (for validation)")
    metadata: Optional[dict] = Field(None, description="Optional metadata to attach to the upload")


class ConfirmUploadRequest(BaseModel):
    """Request model for confirming an upload."""
    
    job_id: str = Field(..., description="Job ID from presigned URL response")
    s3_key: str = Field(..., description="S3 key where file was uploaded")
    metadata: Optional[dict] = Field(None, description="Optional metadata for the processing job")


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def generate_presigned_url(request: PresignedUrlRequest):
    """Generate a presigned S3 URL for direct file upload.
    
    This endpoint:
    1. Validates the filename and file type
    2. Generates a unique job ID and S3 key
    3. Creates a presigned S3 URL for PUT upload
    4. Returns the URL and job ID
    
    The client should:
    1. Upload the file to the presigned URL using PUT method
    2. Call /api/v1/upload/confirm with the job_id and s3_key
    
    Args:
        request: PresignedUrlRequest with filename and optional metadata
        
    Returns:
        PresignedUrlResponse with upload URL, S3 key, and job ID
        
    Raises:
        HTTPException: If filename validation fails
    """
    logger.info(f"Generating presigned URL for: {request.filename}")
    
    # Validate file type
    file_ext = None
    if request.filename:
        file_ext = "." + request.filename.rsplit(".", 1)[-1].lower()
    
    if not file_ext or file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Validate file size if provided
    if request.file_size and request.file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024**3):.1f} GB"
        )
    
    try:
        # Initialize services
        settings = Settings()
        s3_service = S3Service(settings)
        
        # Generate job ID and S3 key
        job_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = request.filename.replace(" ", "_").replace("/", "_")
        s3_key = f"uploads/{timestamp}_{job_id[:8]}_{safe_filename}"
        
        # Determine content type from file extension
        content_type_map = {
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".avi": "video/x-msvideo",
            ".mkv": "video/x-matroska",
            ".webm": "video/webm",
        }
        content_type = content_type_map.get(file_ext, "video/mp4")
        
        # Generate presigned URL (expires in 1 hour)
        expiration = 3600
        upload_url = s3_service.generate_presigned_url(
            s3_key=s3_key,
            expiration=expiration,
            http_method="PUT",
            content_type=content_type
        )
        
        logger.info(f"Generated presigned URL for job {job_id}: {s3_key}")
        
        return PresignedUrlResponse(
            upload_url=upload_url,
            s3_key=s3_key,
            expires_in=expiration,
            job_id=job_id,
            message="Upload file to the provided URL using PUT method, then call /api/v1/upload/confirm"
        )
    
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned URL: {str(e)}"
        )


@router.post("/confirm", response_model=UploadResponse)
async def confirm_upload(request: ConfirmUploadRequest):
    """Confirm an upload and create a processing job.
    
    This endpoint:
    1. Verifies the file exists in S3
    2. Validates the file (if ffprobe is available)
    3. Creates a processing job and enqueues it
    4. Returns job status
    
    Args:
        request: ConfirmUploadRequest with job_id, s3_key, and optional metadata
        
    Returns:
        UploadResponse with job_id and status
        
    Raises:
        HTTPException: If file validation or job creation fails
    """
    logger.info(f"Confirming upload for job {request.job_id}: {request.s3_key}")
    
    try:
        # Initialize services
        settings = Settings()
        s3_service = S3Service(settings)
        video_service = VideoService(settings)
        
        # Verify file exists in S3
        if not s3_service.file_exists(request.s3_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found in S3: {request.s3_key}. Please upload the file first."
            )
        
        # Get file metadata
        file_metadata = s3_service.get_file_metadata(request.s3_key)
        if not file_metadata:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve file metadata from S3"
            )
        
        file_size = file_metadata.get("size", 0)
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty"
            )
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024**3):.1f} GB"
            )
        
        # Optional: Quick validation - check MP4 signature (first 1KB)
        # Note: Full validation happens in the processor, so this is just a quick check
        try:
            # Download first 1KB to check MP4 signature
            s3_response = s3_service.client.get_object(
                Bucket=s3_service._bucket_name,
                Key=request.s3_key,
                Range="bytes=0-1023"
            )
            sample = s3_response['Body'].read()
            
            # Check for MP4 signature (ftyp box)
            if len(sample) >= 12 and sample[4:8] == b'ftyp':
                logger.info(f"Video file signature validated: {request.s3_key}")
            else:
                logger.warning(f"File may not be a valid MP4 (no ftyp signature found): {request.s3_key}")
        except Exception as e:
            # Validation is optional - log warning but continue
            logger.debug(f"Could not validate file signature (non-blocking): {e}")
        
        # Create processing job using the existing S3 file
        job = video_service.create_job_from_s3(
            job_id=request.job_id,
            s3_key=request.s3_key,
            metadata=request.metadata
        )
        
        # Estimate completion time (rough estimate: 1 minute per 10 minutes of video)
        estimated_completion = datetime.utcnow() + timedelta(minutes=30)
        
        logger.info(f"Upload confirmed and job created: {job.job_id}")
        
        return UploadResponse(
            job_id=job.job_id,
            status="queued",
            video_url=f"s3://{job.video_s3_bucket}/{job.video_s3_key}",
            estimated_completion=estimated_completion,
            message="Video upload confirmed and processing queued"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to confirm upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to confirm upload: {str(e)}"
        )


__all__ = ["router"]
