"""
Dispatcher Lambda: consumes SQS, checks idempotency, creates queued job record,
starts ECS RunTask. Deletes SQS message only after task is successfully started.
"""

import json
import logging
import os
import uuid

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    if "Records" not in event or not event["Records"]:
        return {"statusCode": 200, "dispatched": 0}

    region = os.environ.get("AWS_REGION", "us-east-1")
    cluster = os.environ["ECS_CLUSTER"]
    task_def = os.environ["ECS_TASK_DEFINITION"]
    subnets = json.loads(os.environ["ECS_SUBNETS"])
    security_groups = json.loads(os.environ.get("ECS_SECURITY_GROUPS", "[]"))
    bucket = os.environ["S3_BUCKET"]
    idempotency_table = os.environ["IDEMPOTENCY_TABLE_NAME"]
    jobs_table = os.environ["JOBS_TABLE_NAME"]
    queue_url = os.environ["SQS_QUEUE_URL"]

    s3 = boto3.client("s3", region_name=region)
    dynamo = boto3.client("dynamodb", region_name=region)
    ecs = boto3.client("ecs", region_name=region)
    sqs = boto3.client("sqs", region_name=region)

    dispatched = 0
    for record in event["Records"]:
        receipt_handle = record["receiptHandle"]
        body = json.loads(record.get("body", "{}"))

        job_id, s3_key, s3_bucket, is_s3_event = _parse_message(body, bucket)
        if not s3_key:
            logger.warning("Skip invalid message: missing s3_key")
            _delete_message(sqs, queue_url, receipt_handle)
            continue
        if not is_s3_event and not job_id:
            logger.warning("Skip invalid ProcessingJob message: missing job_id")
            _delete_message(sqs, queue_url, receipt_handle)
            continue

        # HeadObject for ETag
        try:
            r = s3.head_object(Bucket=s3_bucket, Key=s3_key)
            etag = (r.get("ETag") or "").strip('"')
        except Exception as e:
            logger.error("HeadObject failed for %s: %s", s3_key, e)
            raise

        # Job ID mismatch fix: only process using the confirm-created job_id (frontend tracks that).
        # - S3 event: if no queued job for this s3_key, skip and wait for confirm message.
        # - S3 event with existing queued job: use that job_id (confirm created first).
        # - ProcessingJob (confirm): always use job_id from body.
        if is_s3_event:
            existing = _find_queued_job_by_s3_key(dynamo, jobs_table, s3_key)
            if existing:
                logger.info(
                    "Using existing queued job %s for s3_key %s (confirm created first)",
                    existing,
                    s3_key[:60],
                )
                job_id = existing
            else:
                logger.info(
                    "S3 event for s3_key=%s but no confirm-created job yet; skip, wait for confirm",
                    s3_key[:80],
                )
                _delete_message(sqs, queue_url, receipt_handle)
                continue

        # Idempotency: claim (s3_key|etag) with conditional PutItem; skip if already claimed/processed
        key = f"{s3_key}|{etag}"
        try:
            dynamo.put_item(
                TableName=idempotency_table,
                Item={
                    "idempotency_key": {"S": key},
                    "s3_key": {"S": s3_key},
                    "etag": {"S": etag},
                    "status": {"S": "dispatched"},
                },
                ConditionExpression="attribute_not_exists(idempotency_key)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.info("Idempotent skip (already claimed): %s", key[:80])
                _delete_message(sqs, queue_url, receipt_handle)
                continue
            raise
        except Exception as e:
            logger.warning("Idempotency claim failed (proceed): %s", e)

        # Create queued job record if not exists (confirm may have already created it).
        # Option A: confirm creates job before SQS; dispatcher only RunTasks and updates task_arn.
        now = _utc_now_iso()
        try:
            dynamo.put_item(
                TableName=jobs_table,
                Item={
                    "job_id": {"S": job_id},
                    "status": {"S": "queued"},
                    "current_stage": {"S": "queued"},
                    "s3_key": {"S": s3_key},
                    "s3_bucket": {"S": s3_bucket},
                    "etag": {"S": etag},
                    "created_at": {"S": now},
                    "updated_at": {"S": now},
                },
                ConditionExpression="attribute_not_exists(job_id)",
            )
            logger.info("Created job %s status=queued", job_id)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.info("Job %s already exists (created by confirm), skipping create", job_id)
            else:
                logger.warning("Jobs put_item failed (non-fatal): %s", e)
        except Exception as e:
            logger.warning("Jobs put_item failed (non-fatal): %s", e)

        # RunTask
        env = [
            {"name": "JOB_ID", "value": job_id},
            {"name": "S3_BUCKET", "value": s3_bucket},
            {"name": "S3_KEY", "value": s3_key},
            {"name": "JOBS_TABLE_NAME", "value": jobs_table},
            {"name": "IDEMPOTENCY_TABLE_NAME", "value": idempotency_table},
            {"name": "AWS_S3_BUCKET_NAME", "value": s3_bucket},
        ]

        nc = {
            "awsvpcConfiguration": {
                "subnets": subnets,
                "assignPublicIp": "ENABLED",
            }
        }
        if security_groups:
            nc["awsvpcConfiguration"]["securityGroups"] = security_groups

        try:
            out = ecs.run_task(
                cluster=cluster,
                taskDefinition=task_def,
                launchType="FARGATE",
                networkConfiguration=nc,
                overrides={
                    "containerOverrides": [
                        {
                            "name": "processor",
                            "environment": env,
                        }
                    ],
                },
            )
        except Exception as e:
            logger.error("RunTask failed: %s", e)
            raise

        failures = out.get("failures", [])
        tasks = out.get("tasks", [])
        if failures or not tasks:
            msg = f"RunTask failed: {failures}"
            logger.error(msg)
            raise RuntimeError(msg)

        task_arn = tasks[0].get("taskArn", "")
        logger.info("Started task %s for job %s", task_arn, job_id)

        # Update job with task_arn
        try:
            dynamo.update_item(
                TableName=jobs_table,
                Key={"job_id": {"S": job_id}},
                UpdateExpression="SET task_arn = :ta, updated_at = :ua",
                ExpressionAttributeValues={
                    ":ta": {"S": task_arn},
                    ":ua": {"S": _utc_now_iso()},
                },
            )
        except Exception as e:
            logger.warning("Update job task_arn failed (non-fatal): %s", e)

        _delete_message(sqs, queue_url, receipt_handle)
        dispatched += 1

    return {"statusCode": 200, "dispatched": dispatched}


def _utc_now_iso():
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


def _is_s3_event(body):
    """True if message is from S3 notification (no job_id; we normally generate one)."""
    if not isinstance(body, dict) or "Records" not in body:
        return False
    rec = (body.get("Records") or [{}])[0]
    return isinstance(rec.get("s3"), dict)


def _find_queued_job_by_s3_key(dynamo, jobs_table: str, s3_key: str):
    """Scan for a queued job with this s3_key (e.g. created by confirm). Return job_id or None."""
    try:
        r = dynamo.scan(
            TableName=jobs_table,
            FilterExpression="s3_key = :k AND #st = :q",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":k": {"S": s3_key}, ":q": {"S": "queued"}},
            Limit=1,
            ProjectionExpression="job_id",
        )
        items = r.get("Items") or []
        if items:
            return (items[0].get("job_id") or {}).get("S")
    except Exception as e:
        logger.warning("Scan for queued job by s3_key failed: %s", e)
    return None


def _parse_message(body, default_bucket):
    """Return (job_id, s3_key, s3_bucket, is_s3_event). Supports ProcessingJob and S3 event."""
    if _is_s3_event(body):
        rec = (body.get("Records") or [{}])[0]
        s3_info = rec.get("s3") or {}
        b = (s3_info.get("bucket") or {}).get("name") or default_bucket
        o = (s3_info.get("object") or {}).get("key") or ""
        job_id = str(uuid.uuid4())
        return (job_id, o, b, True)

    job_id = body.get("job_id") or ""
    s3_key = body.get("video_s3_key") or ""
    s3_bucket = body.get("video_s3_bucket") or default_bucket
    return (job_id, s3_key, s3_bucket, False)


def _delete_message(sqs, queue_url, receipt_handle):
    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
