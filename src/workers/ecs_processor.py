"""
ECS processor entrypoint: run as container main process.

Reads JOB_ID, S3_BUCKET, S3_KEY (and optional config) from env.
Downloads input from S3, runs pipeline, uploads results, updates DynamoDB job
(started, per-stage progress, completed/failed + timings). On any exception:
mark failed, upload failure report to S3, then exit.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import traceback
from pathlib import Path

from config.settings import Settings
from src.main import process_video, process_video_streaming
from src.storage.s3_service import S3Service
from src.utils.timing import stage_timing
from src.utils.idempotency import mark_processed
from src.utils.jobs_store import update_job_status
from src.memory.index_builder import index_daily_summary
from src.memory.store_factory import create_vector_store
from src.memory.embeddings import OpenAIEmbeddingModel

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _progress_update(
    job_id: str,
    jobs_table: str,
    region: str,
    status: str,
    current_stage: str,
    timings: dict[str, int],
) -> None:
    update_job_status(
        job_id,
        status,
        table_name=jobs_table,
        region=region,
        current_stage=current_stage,
        timings=timings,
    )


def _upload_failure_report(
    s3: S3Service,
    s3_bucket: str,
    job_id: str,
    error: str,
    tb: str,
    timings: dict[str, int],
) -> str:
    """Write failure_report.json to temp, upload to S3. Returns result S3 key."""
    report = {
        "job_id": job_id,
        "status": "failed",
        "error": error,
        "traceback": tb,
        "timings": timings,
    }
    # Use work dir from settings
    tmp = Path(s3.settings.temp_dir) / "failure_report.json"
    tmp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    key = f"results/{job_id}/failure_report.json"
    res = s3.upload_file(tmp, key, content_type="application/json")
    if not res.success:
        logger.warning("Failed to upload failure report: %s", res.error)
        return ""
    return key


def main() -> int:
    job_id = os.environ.get("JOB_ID", "").strip()
    s3_bucket = os.environ.get("S3_BUCKET", "").strip()
    s3_key = os.environ.get("S3_KEY", "").strip()
    jobs_table = os.environ.get("JOBS_TABLE_NAME", "").strip()
    idempotency_table = os.environ.get("IDEMPOTENCY_TABLE_NAME", "").strip()
    work_dir = os.environ.get("WORK_DIR", "/tmp").strip()
    region = os.environ.get("AWS_REGION", "us-east-1")

    if not job_id or not s3_bucket or not s3_key:
        logger.error("Missing JOB_ID, S3_BUCKET, or S3_KEY")
        return 1

    temp_dir = Path(work_dir) / f"lifestream_{job_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    local_video = temp_dir / Path(s3_key).name

    settings = Settings()
    settings.temp_dir = str(temp_dir)
    settings.output_dir = str(temp_dir)
    settings.aws_s3_bucket_name = s3_bucket
    settings.aws_region = region
    settings.idempotency_table_name = idempotency_table or None

    timings: dict[str, int] = {}
    s3: S3Service | None = None
    etag = ""
    use_streaming = getattr(settings, "use_streaming_video_intake", True)
    if os.environ.get("USE_STREAMING_VIDEO_INTAKE", "").lower() in ("0", "false", "no"):
        use_streaming = False

    try:
        _progress_update(job_id, jobs_table, region, "processing", "started", timings)

        s3 = S3Service(settings)
        meta = s3.get_file_metadata(s3_key, bucket=s3_bucket)
        etag = (meta or {}).get("etag") or ""

        if use_streaming:
            # Overlap download with audio extraction: presigned URL for ffmpeg stream, background download for scene
            presigned_url = s3.generate_presigned_url(s3_key, expiration=3600, http_method="GET")
            download_done = threading.Event()
            download_error: list[Exception] = []

            def download_worker() -> None:
                try:
                    with stage_timing("download", timings):
                        s3.download_file(s3_key, str(local_video), bucket=s3_bucket)
                except Exception as e:
                    download_error.append(e)
                finally:
                    download_done.set()

            t = threading.Thread(target=download_worker, daemon=False)
            t.start()
            _progress_update(job_id, jobs_table, region, "processing", "download", timings)

            def wait_for_download() -> None:
                download_done.wait()
                if download_error:
                    raise download_error[0]

            video_stem = Path(s3_key).stem
            daily_summary = process_video_streaming(
                video_url=presigned_url,
                local_video_path=str(local_video),
                wait_for_download=wait_for_download,
                video_stem=video_stem,
                settings=settings,
                verbose=False,
                timings=timings,
            )
        else:
            with stage_timing("download", timings):
                s3.download_file(s3_key, str(local_video), bucket=s3_bucket)
            _progress_update(job_id, jobs_table, region, "processing", "download", timings)

            daily_summary = process_video(
                video_path=str(local_video),
                settings=settings,
                verbose=False,
                timings=timings,
            )
        daily_summary.video_source = f"s3://{s3_bucket}/{s3_key}"
        _progress_update(
            job_id, jobs_table, region, "processing", "summarization", timings
        )

        result_key = f"results/{job_id}/summary.json"
        md_key = f"results/{job_id}/summary.md"

        with stage_timing("upload", timings):
            summary_json = daily_summary.model_dump_json(indent=2)
            (temp_dir / "summary.json").write_text(summary_json, encoding="utf-8")
            up = s3.upload_file(
                temp_dir / "summary.json",
                result_key,
                metadata={"job_id": job_id, "video_key": s3_key},
            )
            if not up.success:
                raise RuntimeError(f"Upload summary.json failed: {up.error}")
            from src.processing.summarization import LLMSummarizer

            summarizer = LLMSummarizer(settings)
            md = summarizer.format_markdown_output(daily_summary)
            (temp_dir / "summary.md").write_text(md, encoding="utf-8")
            up_md = s3.upload_file(temp_dir / "summary.md", md_key)
            if not up_md.success:
                raise RuntimeError(f"Upload summary.md failed: {up_md.error}")

        _progress_update(job_id, jobs_table, region, "processing", "upload", timings)

        with stage_timing("indexing", timings):
            try:
                store = create_vector_store(settings)
                embedder = OpenAIEmbeddingModel(settings)
                index_daily_summary(daily_summary, store, embedder)
                logger.info("Summary indexed")
            except Exception as e:
                logger.warning("Indexing failed (non-fatal): %s", e)

        _progress_update(job_id, jobs_table, region, "processing", "indexing", timings)

        mark_processed(s3_key, etag, result_s3_key=result_key, settings=settings)
        update_job_status(
            job_id,
            "completed",
            table_name=jobs_table,
            region=region,
            result_s3_key=result_key,
            current_stage="completed",
            timings=timings,
        )
        logger.info("stage_timings %s", timings)
        logger.info("Job %s completed", job_id)
        return 0

    except Exception as e:
        logger.exception("Job %s failed: %s", job_id, e)
        tb = traceback.format_exc()
        failure_report_key = ""
        if s3 and jobs_table:
            try:
                failure_report_key = _upload_failure_report(
                    s3, s3_bucket, job_id, str(e), tb, timings
                )
            except Exception as ex:
                logger.warning("Could not upload failure report: %s", ex)
        update_job_status(
            job_id,
            "failed",
            table_name=jobs_table,
            region=region,
            error_message=str(e),
            failure_report_s3_key=failure_report_key or None,
            current_stage="failed",
            timings=timings,
        )
        return 1

    finally:
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
