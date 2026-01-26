"""Idempotency for video processing: keyed by S3 object key + ETag.

Ensures each (s3_key, etag) is processed exactly once. Uses DynamoDB.
"""

from __future__ import annotations

import logging
from typing import Optional

from config.settings import Settings

logger = logging.getLogger(__name__)


def _idempotency_key(s3_key: str, etag: str) -> str:
    """Stable key for (s3_key, etag)."""
    # Normalize etag: remove quotes if present
    e = (etag or "").strip().strip('"')
    return f"{s3_key}|{e}"


def is_processed(
    s3_key: str,
    etag: str,
    settings: Optional[Settings] = None,
    *,
    table_name: Optional[str] = None,
) -> bool:
    """Return True if (s3_key, etag) has already been processed."""
    settings = settings or Settings()
    table = table_name or getattr(settings, "idempotency_table_name", None) or ""
    if not table:
        logger.debug("Idempotency table not configured; skipping check")
        return False

    try:
        import boto3
        dynamo = boto3.client("dynamodb", region_name=settings.aws_region)
        key = _idempotency_key(s3_key, etag)
        r = dynamo.get_item(
            TableName=table,
            Key={"idempotency_key": {"S": key}},
            ProjectionExpression="idempotency_key",
        )
        return "Item" in r and len(r["Item"]) > 0
    except Exception as e:
        logger.warning("Idempotency check failed (treating as not processed): %s", e)
        return False


def mark_processed(
    s3_key: str,
    etag: str,
    result_s3_key: Optional[str] = None,
    settings: Optional[Settings] = None,
    *,
    table_name: Optional[str] = None,
) -> None:
    """Record (s3_key, etag) as processed. Call only after successful processing."""
    settings = settings or Settings()
    table = table_name or getattr(settings, "idempotency_table_name", None) or ""
    if not table:
        logger.debug("Idempotency table not configured; skipping mark")
        return

    try:
        import boto3
        from datetime import datetime
        dynamo = boto3.client("dynamodb", region_name=settings.aws_region)
        key = _idempotency_key(s3_key, etag)
        item = {
            "idempotency_key": {"S": key},
            "s3_key": {"S": s3_key},
            "etag": {"S": (etag or "").strip().strip('"')},
            "processed_at": {"S": datetime.utcnow().isoformat() + "Z"},
        }
        if result_s3_key:
            item["result_s3_key"] = {"S": result_s3_key}
        dynamo.put_item(TableName=table, Item=item)
        logger.info("Idempotency marked processed: %s", key[:80])
    except Exception as e:
        logger.warning("Idempotency mark failed (non-fatal): %s", e)
