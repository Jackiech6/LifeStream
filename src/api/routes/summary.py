"""Summary endpoint: read status from DynamoDB, summary content from S3."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Path, Query
from fastapi.responses import Response

from config.settings import Settings
from src.utils.jobs_store import get_job
from src.storage.s3_service import S3Service
from src.api.models.responses import SummaryResponse
from src.models.data_models import DailySummary
from src.processing.summarization import LLMSummarizer

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary/{job_id}", response_model=SummaryResponse)
async def get_summary(
    job_id: str = Path(..., description="Job identifier"),
    format: str = Query("json", description="Response format: 'json' or 'markdown'"),
):
    """Get summary for a completed job.
    
    Uses DynamoDB for status; returns 404 if job not found or not completed.
    Summary content is read from S3 (result_s3_key).
    """
    logger.info("Summary request for job: %s, format: %s", job_id, format)
    settings = Settings()
    table = getattr(settings, "jobs_table_name", None) or ""
    if not table:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JOBS_TABLE_NAME not configured",
        )
    job = get_job(job_id, table_name=table, region=settings.aws_region)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )
    if job.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Summary not available for job {job_id} (status: {job.get('status')})",
        )
    result_key = job.get("result_s3_key")
    if not result_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No result_s3_key for job {job_id}",
        )

    s3 = S3Service(settings)
    bucket = settings.aws_s3_bucket_name or s3._bucket_name
    import tempfile
    from pathlib import Path as PathLib

    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = PathLib(tmpdir) / "summary.json"
        s3.download_file(result_key, local_path, bucket=bucket)
        with open(local_path, "r", encoding="utf-8") as f:
            summary_data = json.load(f)
    daily_summary = DailySummary.model_validate(summary_data)

    md_key = f"results/{job_id}/summary.md"
    if format.lower() == "markdown":
        if s3.file_exists(md_key):
            with tempfile.TemporaryDirectory() as tmpdir:
                local_md = PathLib(tmpdir) / "summary.md"
                s3.download_file(md_key, local_md, bucket=bucket)
                with open(local_md, "r", encoding="utf-8") as f:
                    markdown_content = f.read()
            return Response(
                content=markdown_content,
                media_type="text/markdown",
                headers={"Content-Disposition": f"attachment; filename=summary_{job_id}.md"},
            )
        summarizer = LLMSummarizer(settings)
        markdown_content = summarizer.format_markdown_output(daily_summary)
        return Response(
            content=markdown_content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=summary_{job_id}.md"},
        )

    summarizer = LLMSummarizer(settings)
    markdown_content = summarizer.format_markdown_output(daily_summary)
    return SummaryResponse(
        job_id=job_id,
        date=daily_summary.date,
        video_source=daily_summary.video_source,
        summary_markdown=markdown_content,
        time_blocks=daily_summary.time_blocks,
        video_metadata=daily_summary.video_metadata,
    )


__all__ = ["router"]
