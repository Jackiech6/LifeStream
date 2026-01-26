"""Status endpoint: DynamoDB jobs table as single source of truth."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Path

from config.settings import Settings
from src.utils.jobs_store import get_job, _progress_from_stage_and_timings
from src.api.models.responses import StatusResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str = Path(..., description="Job identifier")):
    """Get job status from DynamoDB (single source of truth).
    
    Returns 404 if job not found. Progress and current_stage come from DynamoDB.
    """
    logger.info("Status request for job: %s", job_id)
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
    st = job.get("status") or "queued"
    stage = job.get("current_stage") or "queued"
    timings = job.get("timings")
    progress = _progress_from_stage_and_timings(stage, timings)
    created = _parse_iso(job.get("created_at") or "")
    updated = _parse_iso(job.get("updated_at") or "")
    return StatusResponse(
        job_id=job_id,
        status=st,
        progress=progress,
        current_stage=stage,
        error=job.get("error_message"),
        timings=timings,
        created_at=created,
        updated_at=updated,
    )


__all__ = ["router"]
