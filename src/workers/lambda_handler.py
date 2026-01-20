"""AWS Lambda handler for video processing.

This module provides the Lambda function entry point for processing videos
uploaded to S3. It downloads the video, processes it using the Stage 1 pipeline,
and uploads results back to S3.
"""

import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from src.main import process_video
from src.storage.s3_service import S3Service
from src.queue.sqs_service import SQSService, ProcessingJob, JobStatus
from src.memory.index_builder import index_daily_summary
from src.memory.store_factory import create_vector_store
from src.memory.embeddings import OpenAIEmbeddingModel
from config.settings import Settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler for processing video files.

    This function is triggered by SQS messages containing video processing jobs.
    It processes the video and updates the job status.

    Args:
        event: Lambda event (SQS message or direct invocation).
        context: Lambda context object.

    Returns:
        Dictionary with status code and message.

    Event Format (SQS):
    {
        "Records": [
            {
                "body": "{\"job_id\": \"...\", \"video_s3_key\": \"...\", ...}",
                "messageAttributes": {...}
            }
        ]
    }
    """
    settings = Settings()

    try:
        # Parse SQS event
        if "Records" in event:
            # SQS event
            records = event["Records"]
            logger.info(f"Received {len(records)} SQS message(s)")

            results = []
            for record in records:
                try:
                    # Parse message body
                    message_body = json.loads(record.get("body", "{}"))
                    job = ProcessingJob.from_dict(message_body)

                    # Process the video
                    result = process_video_job(job, settings)
                    results.append(result)

                except Exception as e:
                    logger.error(f"Failed to process record: {e}", exc_info=True)
                    results.append({"statusCode": 500, "error": str(e)})

            return {"statusCode": 200, "results": results}

        else:
            # Direct invocation (for testing)
            logger.info("Direct invocation (not from SQS)")
            job_data = event.get("job", {})
            job = ProcessingJob.from_dict(job_data) if job_data else None

            if not job:
                # Try to create job from event
                job = ProcessingJob(
                    job_id=event.get("job_id", str(uuid.uuid4())),
                    video_s3_key=event.get("video_s3_key", ""),
                    video_s3_bucket=event.get("video_s3_bucket", settings.aws_s3_bucket_name or ""),
                )

            result = process_video_job(job, settings)
            return result

    except Exception as e:
        logger.error(f"Lambda handler error: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "error": str(e),
        }


def process_video_job(job: ProcessingJob, settings: Settings) -> Dict[str, Any]:
    """Process a single video processing job.

    Args:
        job: ProcessingJob to process.
        settings: Application settings.

    Returns:
        Dictionary with status code and result.
    """
    job.status = JobStatus.PROCESSING
    job.started_at = job.started_at or __import__("datetime").datetime.utcnow().isoformat()

    logger.info(f"Processing job {job.job_id}: {job.video_s3_key}")

    # Use Lambda /tmp directory for temporary files
    temp_dir = Path("/tmp") / f"lifestream_{job.job_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Initialize services
        s3_service = S3Service(settings)
        sqs_service = SQSService(settings)

        # Download video from S3
        local_video_path = temp_dir / Path(job.video_s3_key).name
        logger.info(f"Downloading video from S3: s3://{job.video_s3_bucket}/{job.video_s3_key}")
        s3_service.download_file(job.video_s3_key, local_video_path)

        # Process video using existing pipeline
        logger.info(f"Processing video: {local_video_path}")
        daily_summary = process_video_from_s3(
            s3_bucket=job.video_s3_bucket,
            s3_key=job.video_s3_key,
            local_video_path=str(local_video_path),
            settings=settings,
            temp_dir=str(temp_dir),
        )

        # Upload results to S3
        result_key = f"results/{job.job_id}/summary.json"
        logger.info(f"Uploading results to S3: {result_key}")

        # Serialize summary to JSON
        summary_json = daily_summary.model_dump_json(indent=2)
        summary_path = temp_dir / "summary.json"
        summary_path.write_text(summary_json, encoding="utf-8")

        # Upload JSON summary
        s3_service.upload_file(
            summary_path,
            result_key,
            metadata={"job_id": job.job_id, "video_key": job.video_s3_key},
        )

        # Also upload Markdown summary
        from src.processing.summarization import LLMSummarizer

        summarizer = LLMSummarizer(settings)
        markdown = summarizer.format_markdown_output(daily_summary)
        markdown_path = temp_dir / "summary.md"
        markdown_path.write_text(markdown, encoding="utf-8")

        markdown_key = f"results/{job.job_id}/summary.md"
        s3_service.upload_file(markdown_path, markdown_key)

        # Index summary into vector store (Stage 2)
        logger.info("Indexing summary into vector store")
        try:
            store = create_vector_store(settings)
            embedder = OpenAIEmbeddingModel(settings)
            index_daily_summary(daily_summary, store, embedder)
            logger.info("Summary indexed successfully")
        except Exception as e:
            logger.warning(f"Failed to index summary (non-fatal): {e}")

        # Update job status
        job.status = JobStatus.COMPLETED
        job.completed_at = __import__("datetime").datetime.utcnow().isoformat()
        job.result_s3_key = result_key

        logger.info(f"Job {job.job_id} completed successfully")

        return {
            "statusCode": 200,
            "job_id": job.job_id,
            "status": job.status.value,
            "result_s3_key": result_key,
            "markdown_s3_key": markdown_key,
        }

    except Exception as e:
        logger.error(f"Job {job.job_id} failed: {e}", exc_info=True)

        # Update job status
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.completed_at = __import__("datetime").datetime.utcnow().isoformat()

        # Send to DLQ if configured
        try:
            sqs_service = SQSService(settings)
            sqs_service.send_to_dlq(job, str(e))
        except Exception as dlq_error:
            logger.error(f"Failed to send to DLQ: {dlq_error}")

        return {
            "statusCode": 500,
            "job_id": job.job_id,
            "status": job.status.value,
            "error": str(e),
        }

    finally:
        # Clean up temporary files
        try:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory: {e}")


def process_video_from_s3(
    s3_bucket: str,
    s3_key: str,
    local_video_path: str,
    settings: Optional[Settings] = None,
    temp_dir: Optional[str] = None,
) -> Any:  # Returns DailySummary
    """Process a video downloaded from S3.

    This is a wrapper around the main process_video function that:
    1. Uses S3 paths for metadata
    2. Configures temp directory for Lambda
    3. Handles S3-specific paths

    Args:
        s3_bucket: S3 bucket name.
        s3_key: S3 object key (path).
        local_video_path: Local path to downloaded video file.
        settings: Application settings.
        temp_dir: Temporary directory for processing (defaults to /tmp).

    Returns:
        DailySummary object.
    """
    if settings is None:
        settings = Settings()

    # Override temp_dir for Lambda
    if temp_dir:
        settings.temp_dir = temp_dir
    elif not hasattr(settings, "temp_dir") or not settings.temp_dir:
        settings.temp_dir = "/tmp"

    # Process video using existing pipeline
    # Note: process_video expects local file path, which we have
    daily_summary = process_video(
        video_path=local_video_path,
        settings=settings,
        verbose=False,
    )

    # Update video_source to S3 path
    daily_summary.video_source = f"s3://{s3_bucket}/{s3_key}"

    return daily_summary


__all__ = ["lambda_handler", "process_video_from_s3", "process_video_job"]
