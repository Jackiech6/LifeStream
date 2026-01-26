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
from src.messaging.sqs_service import SQSService, ProcessingJob, JobStatus
from src.memory.index_builder import index_daily_summary
from src.memory.store_factory import create_vector_store
from src.memory.embeddings import OpenAIEmbeddingModel
from src.utils.timing import stage_timing
from src.utils.idempotency import is_processed, mark_processed
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
            # SQS event (may contain ProcessingJob JSON or embedded S3 event JSON)
            records = event["Records"]
            logger.info(f"Received {len(records)} SQS message(s)")

            results = []
            for record in records:
                try:
                    message_body_str = record.get("body", "{}")
                    message_body = json.loads(message_body_str)

                    # Support both direct ProcessingJob dict and S3 event dict
                    job = _build_job_from_message(message_body, settings)

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
                # Try to create job from event (ProcessingJob already imported above)
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


def process_video_job(job: Any, settings: Settings) -> Dict[str, Any]:
    """Process a single video processing job.

    Idempotency: (s3_key, etag) processed at most once. Skip and return 200 if already done.
    """
    job.status = JobStatus.PROCESSING
    job.started_at = job.started_at or __import__("datetime").datetime.utcnow().isoformat()
    logger.info(f"Processing job {job.job_id}: {job.video_s3_key}")

    temp_dir = Path("/tmp") / f"lifestream_{job.job_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    timings: Dict[str, int] = {}
    bucket = job.video_s3_bucket or (settings.aws_s3_bucket_name or "")

    try:
        s3_service = S3Service(settings)
        from src.messaging.sqs_service import SQSService
        sqs_service = SQSService(settings)

        # Get ETag for idempotency (HeadObject)
        meta = s3_service.get_file_metadata(job.video_s3_key, bucket=bucket)
        etag = (meta or {}).get("etag") or ""
        if not etag:
            logger.warning("No ETag for %s; idempotency check skipped", job.video_s3_key)

        if is_processed(job.video_s3_key, etag, settings):
            logger.info("Idempotent skip: already processed s3_key=%s etag=%s", job.video_s3_key, etag[:32] if etag else "")
            return {
                "statusCode": 200,
                "job_id": job.job_id,
                "status": "skipped_idempotent",
                "skipped_idempotent": True,
            }

        # Download
        local_video_path = temp_dir / Path(job.video_s3_key).name
        with stage_timing("download", timings):
            s3_service.download_file(job.video_s3_key, str(local_video_path), bucket=bucket)
        try:
            size_bytes = local_video_path.stat().st_size
        except OSError:
            size_bytes = None
        client_dur = (job.metadata or {}).get("client_duration_seconds")
        size_str = f"{size_bytes} bytes" if size_bytes is not None else "N/A"
        logger.info(
            "Downloaded job_id=%s s3_key=%s local_size=%s path=%s%s",
            job.job_id, job.video_s3_key, size_str, local_video_path,
            f" client_duration_seconds={client_dur}" if client_dur is not None else ""
        )

        # Process pipeline (audio_extraction, diarization, asr, scene_detection, keyframes, sync, summarization)
        logger.info(f"Processing video: {local_video_path}")
        daily_summary = process_video_from_s3(
            s3_bucket=bucket,
            s3_key=job.video_s3_key,
            local_video_path=str(local_video_path),
            settings=settings,
            temp_dir=str(temp_dir),
            timings=timings,
        )

        server_dur = getattr(
            getattr(daily_summary, "video_metadata", None), "duration", None
        )
        if client_dur is not None and server_dur is not None:
            try:
                cd, sd = float(client_dur), float(server_dur)
                diff = abs(cd - sd) / max(sd, 1e-6)
                if diff > 0.2:
                    logger.warning(
                        "Duration mismatch: client=%.1fs, server=%.1fs (diff=%.0f%%). "
                        "Possible wrong file or format vs stream duration mismatch.",
                        cd, sd, diff * 100
                    )
            except (TypeError, ValueError):
                pass

        # Upload results to S3
        result_key = f"results/{job.job_id}/summary.json"
        markdown_key = f"results/{job.job_id}/summary.md"
        with stage_timing("upload", timings):
            summary_json = daily_summary.model_dump_json(indent=2)
            summary_path = temp_dir / "summary.json"
            summary_path.write_text(summary_json, encoding="utf-8")
            s3_service.upload_file(
                summary_path,
                result_key,
                metadata={"job_id": job.job_id, "video_key": job.video_s3_key},
            )
            from src.processing.summarization import LLMSummarizer
            summarizer = LLMSummarizer(settings)
            markdown = summarizer.format_markdown_output(daily_summary)
            markdown_path = temp_dir / "summary.md"
            markdown_path.write_text(markdown, encoding="utf-8")
            s3_service.upload_file(markdown_path, markdown_key)

        with stage_timing("indexing", timings):
            try:
                store = create_vector_store(settings)
                embedder = OpenAIEmbeddingModel(settings)
                index_daily_summary(daily_summary, store, embedder)
                logger.info("Summary indexed successfully")
            except Exception as e:
                logger.warning(f"Failed to index summary (non-fatal): {e}")

        mark_processed(job.video_s3_key, etag, result_s3_key=result_key, settings=settings)

        job.status = JobStatus.COMPLETED
        job.completed_at = __import__("datetime").datetime.utcnow().isoformat()
        job.result_s3_key = result_key

        logger.info("stage_timings %s", timings)
        logger.info(f"Job {job.job_id} completed successfully")

        return {
            "statusCode": 200,
            "job_id": job.job_id,
            "status": job.status.value,
            "result_s3_key": result_key,
            "markdown_s3_key": markdown_key,
            "stage_timings": timings,
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
 

def _build_job_from_message(message_body: Dict[str, Any], settings: Settings):
    """Build a ProcessingJob from a generic message body.

    Supports:
    - Direct ProcessingJob dict (legacy behavior)
    - S3 event dict embedded in an SQS message body
    """
    # S3 event style: {"Records": [...{"s3": {"bucket": {"name": ...}, "object": {"key": ...}}}...]}
    if isinstance(message_body, dict) and "Records" in message_body:
        records = message_body.get("Records") or []
        if records:
            rec = records[0]
            s3_info = (rec.get("s3") or {})
            bucket = (s3_info.get("bucket") or {}).get("name") or (settings.aws_s3_bucket_name or "")
            obj = (s3_info.get("object") or {})
            key = obj.get("key") or ""

            job_id = (
                rec.get("responseElements", {}).get("x-amz-request-id")
                or rec.get("eventID")
                or str(uuid.uuid4())
            )

            return ProcessingJob(
                job_id=job_id,
                video_s3_key=key,
                video_s3_bucket=bucket,
            )

    # Fallback: assume this is already a ProcessingJob dict
    return ProcessingJob.from_dict(message_body)


def process_video_from_s3(
    s3_bucket: str,
    s3_key: str,
    local_video_path: str,
    settings: Optional[Settings] = None,
    temp_dir: Optional[str] = None,
    timings: Optional[Dict[str, int]] = None,
) -> Any:  # Returns DailySummary
    """Process a video downloaded from S3.

    Uses S3 paths for metadata, configures temp directory, passes timings to process_video.
    """
    if settings is None:
        settings = Settings()
    if temp_dir:
        settings.temp_dir = temp_dir
    elif not getattr(settings, "temp_dir", None):
        settings.temp_dir = "/tmp"

    daily_summary = process_video(
        video_path=local_video_path,
        settings=settings,
        verbose=False,
        timings=timings,
    )
    daily_summary.video_source = f"s3://{s3_bucket}/{s3_key}"
    return daily_summary


__all__ = ["lambda_handler", "process_video_from_s3", "process_video_job"]
