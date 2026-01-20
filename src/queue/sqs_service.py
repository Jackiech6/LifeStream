"""SQS service for event-driven video processing.

This module provides a Python service for interacting with AWS SQS,
handling video processing job messages.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

import boto3
from botocore.exceptions import ClientError

from config.settings import Settings

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Processing job status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProcessingJob:
    """Video processing job message."""

    job_id: str
    video_s3_key: str
    video_s3_bucket: str
    status: JobStatus = JobStatus.PENDING
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    result_s3_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingJob":
        """Create from dictionary."""
        if "status" in data and isinstance(data["status"], str):
            data["status"] = JobStatus(data["status"])
        return cls(**data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> "ProcessingJob":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


class SQSService:
    """Service for interacting with AWS SQS for video processing jobs."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize SQS service.

        Args:
            settings: Application settings. If None, creates default settings.

        Raises:
            ValueError: If SQS queue URL is not configured.
        """
        self.settings = settings or Settings()
        self.queue_url = self.settings.aws_sqs_queue_url
        self.dlq_url = self.settings.aws_sqs_dlq_url
        self.region = self.settings.aws_region

        if not self.queue_url:
            raise ValueError("SQS_QUEUE_URL must be set in settings or environment.")

        self._sqs_client = boto3.client("sqs", region_name=self.region)
        logger.info(f"SQSService initialized for queue: {self.queue_url}")

    def send_processing_job(self, job: ProcessingJob) -> str:
        """Send a processing job to the queue.

        Args:
            job: ProcessingJob object to enqueue.

        Returns:
            Message ID from SQS.

        Raises:
            ClientError: If SQS operation fails.
        """
        try:
            message_body = job.to_json()
            message_attributes = {
                "job_id": {
                    "StringValue": job.job_id,
                    "DataType": "String",
                },
                "status": {
                    "StringValue": job.status.value,
                    "DataType": "String",
                },
            }

            response = self._sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body,
                MessageAttributes=message_attributes,
            )

            message_id = response["MessageId"]
            logger.info(f"Sent processing job {job.job_id} to queue (MessageId: {message_id})")
            return message_id

        except ClientError as e:
            logger.error(f"Failed to send job to SQS: {e}")
            raise RuntimeError(f"SQS send_message failed: {e}") from e

    def receive_job(self, max_messages: int = 1, wait_time_seconds: int = 20) -> List[ProcessingJob]:
        """Receive processing jobs from the queue.

        Args:
            max_messages: Maximum number of messages to receive (1-10).
            wait_time_seconds: Long polling wait time (0-20 seconds).

        Returns:
            List of ProcessingJob objects.

        Raises:
            ClientError: If SQS operation fails.
        """
        try:
            response = self._sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=wait_time_seconds,
                MessageAttributeNames=["All"],
            )

            messages = response.get("Messages", [])
            jobs = []

            for msg in messages:
                try:
                    job = ProcessingJob.from_json(msg["Body"])
                    # Store receipt handle for deletion
                    job.metadata = job.metadata or {}
                    job.metadata["_receipt_handle"] = msg["ReceiptHandle"]
                    job.metadata["_message_id"] = msg["MessageId"]
                    jobs.append(job)
                    logger.debug(f"Received job {job.job_id} from queue")
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse message: {e}")
                    continue

            return jobs

        except ClientError as e:
            logger.error(f"Failed to receive messages from SQS: {e}")
            raise RuntimeError(f"SQS receive_message failed: {e}") from e

    def delete_job(self, job: ProcessingJob) -> None:
        """Delete a processed job from the queue.

        Args:
            job: ProcessingJob with receipt handle in metadata.

        Raises:
            ValueError: If receipt handle not found.
            ClientError: If SQS operation fails.
        """
        if not job.metadata or "_receipt_handle" not in job.metadata:
            raise ValueError("Job metadata must contain receipt_handle for deletion")

        receipt_handle = job.metadata["_receipt_handle"]

        try:
            self._sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
            )
            logger.info(f"Deleted job {job.job_id} from queue")

        except ClientError as e:
            logger.error(f"Failed to delete message from SQS: {e}")
            raise RuntimeError(f"SQS delete_message failed: {e}") from e

    def get_queue_attributes(self) -> Dict[str, Any]:
        """Get queue attributes (approximate number of messages, etc.).

        Returns:
            Dictionary of queue attributes.

        Raises:
            ClientError: If SQS operation fails.
        """
        try:
            response = self._sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=["All"],
            )
            return response.get("Attributes", {})

        except ClientError as e:
            logger.error(f"Failed to get queue attributes: {e}")
            raise RuntimeError(f"SQS get_queue_attributes failed: {e}") from e

    def purge_queue(self) -> None:
        """Purge all messages from the queue.

        Warning: This operation cannot be undone.

        Raises:
            ClientError: If SQS operation fails.
        """
        try:
            self._sqs_client.purge_queue(QueueUrl=self.queue_url)
            logger.warning(f"Purged all messages from queue: {self.queue_url}")

        except ClientError as e:
            logger.error(f"Failed to purge queue: {e}")
            raise RuntimeError(f"SQS purge_queue failed: {e}") from e

    def send_to_dlq(self, job: ProcessingJob, error_message: str) -> None:
        """Send a failed job to the dead-letter queue.

        Args:
            job: ProcessingJob that failed.
            error_message: Error message describing the failure.

        Raises:
            ClientError: If SQS operation fails.
        """
        if not self.dlq_url:
            logger.warning("DLQ URL not configured, cannot send to DLQ")
            return

        try:
            job.status = JobStatus.FAILED
            job.error_message = error_message
            job.completed_at = datetime.utcnow().isoformat()

            message_body = job.to_json()
            self._sqs_client.send_message(
                QueueUrl=self.dlq_url,
                MessageBody=message_body,
            )

            logger.info(f"Sent failed job {job.job_id} to DLQ: {error_message}")

        except ClientError as e:
            logger.error(f"Failed to send job to DLQ: {e}")
            raise RuntimeError(f"SQS send_message to DLQ failed: {e}") from e


__all__ = ["SQSService", "ProcessingJob", "JobStatus"]
