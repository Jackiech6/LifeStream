"""Video service for handling video uploads and processing jobs.

This service coordinates between S3, SQS, and the processing pipeline.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from src.storage.s3_service import S3Service
from src.queue.sqs_service import SQSService, ProcessingJob, JobStatus
from config.settings import Settings

logger = logging.getLogger(__name__)


class VideoService:
    """Service for managing video uploads and processing jobs."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize VideoService.

        Args:
            settings: Application settings. If None, creates default settings.
        """
        self.settings = settings or Settings()
        self.s3_service = S3Service(self.settings)
        self.sqs_service = SQSService(self.settings)

    def create_upload_job(
        self,
        video_file_path: str,
        s3_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessingJob:
        """Create a processing job for an uploaded video.

        Args:
            video_file_path: Local path to video file.
            s3_key: Optional S3 key (auto-generated if None).
            metadata: Optional metadata to attach to job.

        Returns:
            ProcessingJob object.

        Raises:
            FileNotFoundError: If video file doesn't exist.
            RuntimeError: If upload or enqueue fails.
        """
        video_path = Path(video_file_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_file_path}")

        # Generate job ID and S3 key
        job_id = str(uuid.uuid4())
        if not s3_key:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key = f"uploads/{timestamp}_{video_path.name}"

        # Upload video to S3
        logger.info(f"Uploading video to S3: {s3_key}")
        s3_service = S3Service(self.settings)
        s3_service.upload_file(
            video_path,
            s3_key,
            metadata={
                "job_id": job_id,
                "original_filename": video_path.name,
                "uploaded_at": datetime.utcnow().isoformat(),
                **(metadata or {}),
            },
        )

        # Create processing job
        job = ProcessingJob(
            job_id=job_id,
            video_s3_key=s3_key,
            video_s3_bucket=self.settings.aws_s3_bucket_name or s3_service.bucket_name,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow().isoformat(),
            metadata=metadata or {},
        )

        # Enqueue job (S3 notification will also trigger, but this ensures it's queued)
        logger.info(f"Enqueuing processing job: {job_id}")
        self.sqs_service.send_processing_job(job)

        logger.info(f"Created upload job {job_id} for {s3_key}")
        return job

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a processing job.

        Note: This is a simplified implementation. In production, you'd query
        a database or use a job tracking service.

        Args:
            job_id: Job ID to look up.

        Returns:
            Dictionary with job status, or None if not found.
        """
        # In a real implementation, this would query a database
        # For now, we can't easily track job status without a database
        # This would be implemented in Stage 3.4 (Database & State Management)
        logger.warning("get_job_status not fully implemented (requires database)")
        return None

    def generate_presigned_upload_url(
        self,
        filename: str,
        expiration: int = 3600,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Generate a presigned URL for direct client upload to S3.

        Args:
            filename: Name of the file to upload.
            expiration: URL expiration time in seconds (default: 1 hour).
            metadata: Optional metadata to include with upload.

        Returns:
            Dictionary with 'url' and 's3_key' keys.
        """
        # Generate S3 key
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        s3_key = f"uploads/{timestamp}_{filename}"

        # Generate presigned URL
        url = self.s3_service.generate_presigned_url(s3_key, expiration=expiration)

        return {
            "url": url,
            "s3_key": s3_key,
            "expires_in": expiration,
        }


__all__ = ["VideoService"]
