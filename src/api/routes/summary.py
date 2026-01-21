"""Summary endpoint for retrieving video summaries."""

import logging
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Path, Query
from fastapi.responses import Response

from config.settings import Settings
from src.storage.s3_service import S3Service
from src.api.models.responses import SummaryResponse
from src.models.data_models import DailySummary
from src.processing.summarization import LLMSummarizer

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary/{job_id}", response_model=SummaryResponse)
async def get_summary(
    job_id: str = Path(..., description="Job identifier"),
    format: str = Query("json", description="Response format: 'json' or 'markdown'")
):
    """Get the summary for a completed processing job.
    
    Args:
        job_id: Job identifier
        format: Response format ('json' or 'markdown')
        
    Returns:
        SummaryResponse or Markdown text
        
    Raises:
        HTTPException: If job not found or not completed
    """
    logger.info(f"Summary request for job: {job_id}, format: {format}")
    
    try:
        settings = Settings()
        s3_service = S3Service(settings)
        
        # Check for result files
        result_key = f"results/{job_id}/summary.json"
        markdown_key = f"results/{job_id}/summary.md"
        
        if not s3_service.file_exists(result_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Summary not found for job {job_id}. Job may still be processing."
            )
        
        # Download summary JSON
        import tempfile
        from pathlib import Path as PathLib
        
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = PathLib(tmpdir) / "summary.json"
            s3_service.download_file(result_key, local_path)
            
            # Parse JSON
            with open(local_path, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
            
            daily_summary = DailySummary.model_validate(summary_data)
        
        # If markdown format requested, return markdown directly
        if format.lower() == "markdown":
            if s3_service.file_exists(markdown_key):
                with tempfile.TemporaryDirectory() as tmpdir:
                    local_path = PathLib(tmpdir) / "summary.md"
                    s3_service.download_file(markdown_key, local_path)
                    
                    with open(local_path, "r", encoding="utf-8") as f:
                        markdown_content = f.read()
                
                return Response(
                    content=markdown_content,
                    media_type="text/markdown",
                    headers={"Content-Disposition": f"attachment; filename=summary_{job_id}.md"}
                )
            else:
                # Generate markdown from JSON
                summarizer = LLMSummarizer(settings)
                markdown_content = summarizer.format_markdown_output(daily_summary)
                
                return Response(
                    content=markdown_content,
                    media_type="text/markdown",
                    headers={"Content-Disposition": f"attachment; filename=summary_{job_id}.md"}
                )
        
        # Generate markdown for JSON response
        summarizer = LLMSummarizer(settings)
        markdown_content = summarizer.format_markdown_output(daily_summary)
        
        # Return JSON response
        return SummaryResponse(
            job_id=job_id,
            date=daily_summary.date,
            video_source=daily_summary.video_source,
            summary_markdown=markdown_content,
            time_blocks=daily_summary.time_blocks,
            video_metadata=daily_summary.video_metadata
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get summary for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summary: {str(e)}"
        )


__all__ = ["router"]
