"""Job status metadata store (DynamoDB). Single source of truth for status and timings.

Used by dispatcher (create queued), ECS processor (started, progress, completed/failed),
and API (GET status, GET summary).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Known stages for progress weighting (0–1). Order matters for progress estimate.
STAGE_ORDER = [
    "started",
    "download",
    "audio_extraction",
    "diarization",
    "asr",
    "scene_detection",
    "keyframes",
    "sync",
    "summarization",
    "upload",
    "indexing",
    "completed",
]


def _progress_from_stage_and_timings(current_stage: str, timings: Optional[Dict[str, int]]) -> float:
    """Compute progress in [0, 1] from current_stage and timings."""
    if current_stage == "completed":
        return 1.0
    if current_stage == "failed":
        return 1.0  # terminal
    if current_stage == "queued":
        return 0.0
    n = len(STAGE_ORDER)
    try:
        i = STAGE_ORDER.index(current_stage)
        return (i + 1) / n
    except ValueError:
        return 0.5


def get_job(
    job_id: str,
    *,
    table_name: str,
    region: str = "us-east-1",
) -> Optional[Dict[str, Any]]:
    """Fetch job by job_id from DynamoDB. Returns None if not found."""
    if not table_name:
        return None
    try:
        import boto3
        dynamo = boto3.client("dynamodb", region_name=region)
        r = dynamo.get_item(
            TableName=table_name,
            Key={"job_id": {"S": job_id}},
        )
        item = r.get("Item")
        if not item:
            return None

        def _s(k: str) -> str:
            v = item.get(k, {}).get("S")
            return v or ""

        def _n(k: str) -> Optional[int]:
            v = item.get(k, {}).get("N")
            return int(v) if v is not None else None

        timings_raw = _s("timings")
        timings: Optional[Dict[str, int]] = None
        if timings_raw:
            try:
                timings = json.loads(timings_raw)
            except Exception:
                pass

        return {
            "job_id": job_id,
            "status": _s("status"),
            "s3_key": _s("s3_key"),
            "s3_bucket": _s("s3_bucket"),
            "error_message": _s("error_message") or None,
            "result_s3_key": _s("result_s3_key") or None,
            "failure_report_s3_key": _s("failure_report_s3_key") or None,
            "current_stage": _s("current_stage") or None,
            "timings": timings,
            "created_at": _s("created_at"),
            "updated_at": _s("updated_at"),
            "task_arn": _s("task_arn") or None,
        }
    except Exception as e:
        logger.warning("Jobs get_job failed: %s", e)
        return None


def update_job_status(
    job_id: str,
    status: str,
    *,
    table_name: str,
    region: str = "us-east-1",
    error_message: Optional[str] = None,
    result_s3_key: Optional[str] = None,
    failure_report_s3_key: Optional[str] = None,
    current_stage: Optional[str] = None,
    timings: Optional[Dict[str, int]] = None,
    task_arn: Optional[str] = None,
) -> None:
    """Update job status in DynamoDB. Uses UpdateItem for partial updates."""
    if not table_name:
        return
    try:
        import boto3
        dynamo = boto3.client("dynamodb", region_name=region)
        now = datetime.utcnow().isoformat() + "Z"

        updates = [
            "#st = :st",
            "updated_at = :ua",
        ]
        names = {"#st": "status"}
        values: Dict[str, Dict[str, str]] = {
            ":st": {"S": status},
            ":ua": {"S": now},
        }

        if error_message is not None:
            updates.append("error_message = :em")
            values[":em"] = {"S": error_message}
        if result_s3_key is not None:
            updates.append("result_s3_key = :rs")
            values[":rs"] = {"S": result_s3_key}
        if failure_report_s3_key is not None:
            updates.append("failure_report_s3_key = :fr")
            values[":fr"] = {"S": failure_report_s3_key}
        if current_stage is not None:
            updates.append("current_stage = :cs")
            values[":cs"] = {"S": current_stage}
        if timings is not None:
            updates.append("timings = :ti")
            values[":ti"] = {"S": json.dumps(timings)}
        if task_arn is not None:
            updates.append("task_arn = :ta")
            values[":ta"] = {"S": task_arn}

        dynamo.update_item(
            TableName=table_name,
            Key={"job_id": {"S": job_id}},
            UpdateExpression="SET " + ", ".join(updates),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
        logger.info("Updated job %s status=%s", job_id, status)
    except Exception as e:
        logger.warning("Jobs store update failed (non-fatal): %s", e)


def create_job(
    job_id: str,
    *,
    table_name: str,
    region: str = "us-east-1",
    s3_key: str = "",
    s3_bucket: str = "",
    etag: Optional[str] = None,
) -> None:
    """Create a new job record with status=queued. Idempotent: no-op if job_id exists."""
    if not table_name:
        return
    try:
        import boto3
        from botocore.exceptions import ClientError
        dynamo = boto3.client("dynamodb", region_name=region)
        now = datetime.utcnow().isoformat() + "Z"
        item = {
            "job_id": {"S": job_id},
            "status": {"S": "queued"},
            "current_stage": {"S": "queued"},
            "created_at": {"S": now},
            "updated_at": {"S": now},
        }
        if s3_key:
            item["s3_key"] = {"S": s3_key}
        if s3_bucket:
            item["s3_bucket"] = {"S": s3_bucket}
        if etag:
            item["etag"] = {"S": etag}

        dynamo.put_item(
            TableName=table_name,
            Item=item,
            ConditionExpression="attribute_not_exists(job_id)",
        )
        logger.info("Created job %s status=queued", job_id)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.debug("Job %s already exists, skip create", job_id)
            return
        raise
    except Exception as e:
        logger.warning("Jobs create failed (non-fatal): %s", e)


def list_jobs(
    *,
    table_name: str,
    region: str = "us-east-1",
    status_filter: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """List jobs from DynamoDB, optionally filtered by status (e.g. 'completed').

    Returns a list of job dicts with job_id, status, s3_key, s3_bucket, created_at, etc.
    """
    if not table_name:
        return []
    try:
        import boto3
        dynamo = boto3.client("dynamodb", region_name=region)

        def _s(item: Dict[str, Any], k: str) -> str:
            v = (item.get(k) or {}).get("S")
            return v or ""

        def _n(item: Dict[str, Any], k: str) -> Optional[int]:
            v = (item.get(k) or {}).get("N")
            return int(v) if v is not None else None

        scan_kwargs: Dict[str, Any] = {"Limit": limit}
        if status_filter:
            scan_kwargs["FilterExpression"] = "#st = :st"
            scan_kwargs["ExpressionAttributeNames"] = {"#st": "status"}
            scan_kwargs["ExpressionAttributeValues"] = {":st": {"S": status_filter}}

        r = dynamo.scan(TableName=table_name, **scan_kwargs)
        items = r.get("Items") or []
        jobs: List[Dict[str, Any]] = []
        for item in items:
            job_id = _s(item, "job_id")
            if not job_id:
                continue
            timings_raw = _s(item, "timings")
            timings: Optional[Dict[str, int]] = None
            if timings_raw:
                try:
                    timings = json.loads(timings_raw)
                except Exception:
                    pass
            jobs.append({
                "job_id": job_id,
                "status": _s(item, "status"),
                "s3_key": _s(item, "s3_key"),
                "s3_bucket": _s(item, "s3_bucket"),
                "error_message": _s(item, "error_message") or None,
                "result_s3_key": _s(item, "result_s3_key") or None,
                "failure_report_s3_key": _s(item, "failure_report_s3_key") or None,
                "current_stage": _s(item, "current_stage") or None,
                "timings": timings,
                "created_at": _s(item, "created_at"),
                "updated_at": _s(item, "updated_at"),
                "task_arn": _s(item, "task_arn") or None,
            })
        return jobs
    except Exception as e:
        logger.warning("Jobs list_jobs failed: %s", e)
        return []


def delete_job(
    job_id: str,
    *,
    table_name: str,
    region: str = "us-east-1",
) -> bool:
    """Delete a job record by job_id. Returns True if deleted, False if not found or error."""
    if not table_name:
        return False
    try:
        import boto3
        dynamo = boto3.client("dynamodb", region_name=region)
        dynamo.delete_item(
            TableName=table_name,
            Key={"job_id": {"S": job_id}},
        )
        logger.info("Deleted job %s (orphan cleanup)", job_id)
        return True
    except Exception as e:
        logger.warning("Jobs delete_job failed: %s", e)
        return False
