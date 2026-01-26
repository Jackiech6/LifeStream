"""Memory endpoint: list and delete indexed videos and chunks (vector store + DynamoDB)."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status

from config.settings import Settings
from src.utils.jobs_store import list_jobs, get_job, delete_job
from src.memory.store_factory import create_vector_store, get_vector_store_type
from src.api.models.responses import (
    MemoryListResponse,
    MemoryJobItem,
    MemoryChunkItem,
    DeleteChunksResponse,
    DeleteJobsResponse,
)
from src.api.models.requests import DeleteChunksRequest, DeleteJobsRequest

logger = logging.getLogger(__name__)

router = APIRouter()


def _video_id(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}" if bucket and key else ""


@router.get("/memory", response_model=MemoryListResponse)
async def list_memory():
    """List completed jobs (from DynamoDB) and all chunks (from vector store).

    Only supports Pinecone; returns 503 if vector store is not Pinecone.
    Chunk metadata is returned without embeddings.
    """
    settings = Settings()
    if get_vector_store_type(settings) != "pinecone":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory list is only available when using Pinecone vector store.",
        )
    jobs_table = getattr(settings, "jobs_table_name", None) or ""
    if not jobs_table:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JOBS_TABLE_NAME not configured.",
        )
    try:
        store = create_vector_store(settings)
    except Exception as e:
        logger.error("Failed to create vector store: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vector store unavailable: {str(e)}",
        ) from e

    # List completed jobs from DynamoDB
    raw_jobs = list_jobs(
        table_name=jobs_table,
        region=settings.aws_region,
        status_filter="completed",
        limit=500,
    )
    # List chunks from Pinecone (metadata only)
    if not hasattr(store, "list_all_chunks"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store does not support listing chunks.",
        )
    raw_chunks = store.list_all_chunks(prefix="chunk_", limit=5000)

    # Build chunk counts per video_id and job list with video_id
    video_to_count: dict = {}
    job_items: List[MemoryJobItem] = []
    for j in raw_jobs:
        vid = _video_id(j.get("s3_bucket") or "", j.get("s3_key") or "")
        job_items.append(
            MemoryJobItem(
                job_id=j["job_id"],
                s3_key=j.get("s3_key") or "",
                s3_bucket=j.get("s3_bucket") or "",
                video_id=vid,
                status=j.get("status") or "completed",
                created_at=j.get("created_at"),
                chunk_count=0,
            )
        )

    chunk_items: List[MemoryChunkItem] = []
    for c in raw_chunks:
        vid = (c.get("video_id") or "").strip()
        if vid:
            video_to_count[vid] = video_to_count.get(vid, 0) + 1
        # Truncate text for display
        text = c.get("text")
        if isinstance(text, str) and len(text) > 300:
            text = text[:297] + "..."
        chunk_items.append(
            MemoryChunkItem(
                id=c.get("id") or c.get("_id") or "",
                video_id=vid,
                date=c.get("date"),
                start_time=c.get("start_time"),
                end_time=c.get("end_time"),
                source_type=c.get("source_type"),
                text=text,
                metadata={k: v for k, v in c.items() if k not in ("id", "_id", "video_id", "date", "start_time", "end_time", "source_type", "text")},
            )
        )

    for ji in job_items:
        ji.chunk_count = video_to_count.get(ji.video_id, 0)

    return MemoryListResponse(jobs=job_items, chunks=chunk_items)


@router.delete("/memory/chunks", response_model=DeleteChunksResponse)
async def delete_chunks(request: DeleteChunksRequest):
    """Delete chunks from the vector store by ID."""
    settings = Settings()
    if get_vector_store_type(settings) != "pinecone":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory delete is only available when using Pinecone vector store.",
        )
    try:
        store = create_vector_store(settings)
    except Exception as e:
        logger.error("Failed to create vector store: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vector store unavailable: {str(e)}",
        ) from e
    ids = list(request.chunk_ids)
    if not ids:
        return DeleteChunksResponse(deleted=0, chunk_ids=[])
    store.delete(ids)
    return DeleteChunksResponse(deleted=len(ids), chunk_ids=ids)


@router.delete("/memory/jobs", response_model=DeleteJobsResponse)
async def delete_jobs_from_memory(request: DeleteJobsRequest):
    """Delete job records from DynamoDB and remove all their chunks from the vector store."""
    settings = Settings()
    if get_vector_store_type(settings) != "pinecone":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory delete is only available when using Pinecone vector store.",
        )
    jobs_table = getattr(settings, "jobs_table_name", None) or ""
    if not jobs_table:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JOBS_TABLE_NAME not configured.",
        )
    try:
        store = create_vector_store(settings)
    except Exception as e:
        logger.error("Failed to create vector store: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vector store unavailable: {str(e)}",
        ) from e

    if not hasattr(store, "delete_by_filter"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store does not support delete by filter.",
        )

    deleted_jobs = 0
    videos_whose_chunks_deleted = 0
    for job_id in request.job_ids:
        job = get_job(job_id, table_name=jobs_table, region=settings.aws_region)
        if not job:
            logger.warning("Job not found for delete: %s", job_id)
            continue
        video_id = _video_id(job.get("s3_bucket") or "", job.get("s3_key") or "")
        # Delete all chunks for this video first, then remove the job record.
        if video_id:
            try:
                store.delete_by_filter({"video_id": video_id})
                videos_whose_chunks_deleted += 1
                logger.info("Deleted vector store chunks for video_id=%s (job=%s)", video_id[:80], job_id)
            except Exception as e:
                logger.warning("Delete by filter failed for video_id=%s: %s", video_id[:80], e)
        if delete_job(job_id, table_name=jobs_table, region=settings.aws_region):
            deleted_jobs += 1

    return DeleteJobsResponse(
        deleted_jobs=deleted_jobs,
        deleted_chunks=videos_whose_chunks_deleted,
        job_ids=request.job_ids,
    )


__all__ = ["router"]
