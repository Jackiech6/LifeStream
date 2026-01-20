"""Unit tests for SQS service."""

from unittest.mock import MagicMock, patch, Mock
import json
import pytest
from datetime import datetime

from src.queue.sqs_service import SQSService, ProcessingJob, JobStatus
from config.settings import Settings


@pytest.fixture
def mock_sqs_client():
    """Create a mocked SQS client."""
    with patch("src.queue.sqs_service.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def settings_with_sqs():
    """Create settings with SQS configuration."""
    settings = Settings()
    settings.aws_sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
    settings.aws_sqs_dlq_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-dlq"
    settings.aws_region = "us-east-1"
    return settings


def test_sqs_service_initialization(settings_with_sqs, mock_sqs_client):
    """SQSService should initialize with correct settings."""
    service = SQSService(settings_with_sqs)

    assert service.queue_url == settings_with_sqs.aws_sqs_queue_url
    assert service.dlq_url == settings_with_sqs.aws_sqs_dlq_url
    assert service.region == settings_with_sqs.aws_region


def test_sqs_service_missing_queue_url():
    """SQSService should raise error if queue URL not configured."""
    settings = Settings()
    settings.aws_sqs_queue_url = None

    with pytest.raises(ValueError, match="SQS_QUEUE_URL must be set"):
        SQSService(settings)


def test_send_processing_job(settings_with_sqs, mock_sqs_client):
    """send_processing_job should send job to SQS."""
    service = SQSService(settings_with_sqs)

    job = ProcessingJob(
        job_id="test-job-123",
        video_s3_key="uploads/video.mp4",
        video_s3_bucket="test-bucket",
    )

    mock_sqs_client.send_message.return_value = {"MessageId": "msg-123"}

    message_id = service.send_processing_job(job)

    assert message_id == "msg-123"
    mock_sqs_client.send_message.assert_called_once()
    call_kwargs = mock_sqs_client.send_message.call_args[1]
    assert call_kwargs["QueueUrl"] == settings_with_sqs.aws_sqs_queue_url
    assert "job_id" in call_kwargs["MessageAttributes"]


def test_receive_job(settings_with_sqs, mock_sqs_client):
    """receive_job should receive and parse jobs from SQS."""
    service = SQSService(settings_with_sqs)

    # Mock SQS response
    job = ProcessingJob(
        job_id="test-job-123",
        video_s3_key="uploads/video.mp4",
        video_s3_bucket="test-bucket",
    )

    mock_sqs_client.receive_message.return_value = {
        "Messages": [
            {
                "Body": job.to_json(),
                "ReceiptHandle": "receipt-handle-123",
                "MessageId": "msg-123",
            }
        ]
    }

    jobs = service.receive_job()

    assert len(jobs) == 1
    assert jobs[0].job_id == "test-job-123"
    assert jobs[0].metadata["_receipt_handle"] == "receipt-handle-123"


def test_receive_job_empty_queue(settings_with_sqs, mock_sqs_client):
    """receive_job should return empty list when queue is empty."""
    service = SQSService(settings_with_sqs)

    mock_sqs_client.receive_message.return_value = {"Messages": []}

    jobs = service.receive_job()

    assert jobs == []


def test_delete_job(settings_with_sqs, mock_sqs_client):
    """delete_job should delete message from queue."""
    service = SQSService(settings_with_sqs)

    job = ProcessingJob(
        job_id="test-job-123",
        video_s3_key="uploads/video.mp4",
        video_s3_bucket="test-bucket",
        metadata={"_receipt_handle": "receipt-handle-123"},
    )

    service.delete_job(job)

    mock_sqs_client.delete_message.assert_called_once_with(
        QueueUrl=settings_with_sqs.aws_sqs_queue_url,
        ReceiptHandle="receipt-handle-123",
    )


def test_delete_job_missing_receipt_handle(settings_with_sqs, mock_sqs_client):
    """delete_job should raise error if receipt handle missing."""
    service = SQSService(settings_with_sqs)

    job = ProcessingJob(
        job_id="test-job-123",
        video_s3_key="uploads/video.mp4",
        video_s3_bucket="test-bucket",
    )

    with pytest.raises(ValueError, match="receipt_handle"):
        service.delete_job(job)


def test_get_queue_attributes(settings_with_sqs, mock_sqs_client):
    """get_queue_attributes should return queue attributes."""
    service = SQSService(settings_with_sqs)

    mock_sqs_client.get_queue_attributes.return_value = {
        "Attributes": {
            "ApproximateNumberOfMessages": "5",
            "ApproximateNumberOfMessagesNotVisible": "2",
        }
    }

    attributes = service.get_queue_attributes()

    assert "ApproximateNumberOfMessages" in attributes
    assert attributes["ApproximateNumberOfMessages"] == "5"


def test_purge_queue(settings_with_sqs, mock_sqs_client):
    """purge_queue should purge all messages."""
    service = SQSService(settings_with_sqs)

    service.purge_queue()

    mock_sqs_client.purge_queue.assert_called_once_with(
        QueueUrl=settings_with_sqs.aws_sqs_queue_url
    )


def test_send_to_dlq(settings_with_sqs, mock_sqs_client):
    """send_to_dlq should send failed job to dead-letter queue."""
    service = SQSService(settings_with_sqs)

    job = ProcessingJob(
        job_id="test-job-123",
        video_s3_key="uploads/video.mp4",
        video_s3_bucket="test-bucket",
    )

    service.send_to_dlq(job, "Test error")

    assert job.status == JobStatus.FAILED
    assert job.error_message == "Test error"
    mock_sqs_client.send_message.assert_called_once()
    call_kwargs = mock_sqs_client.send_message.call_args[1]
    assert call_kwargs["QueueUrl"] == settings_with_sqs.aws_sqs_dlq_url


def test_send_to_dlq_no_dlq_configured(settings_with_sqs, mock_sqs_client):
    """send_to_dlq should warn if DLQ not configured."""
    settings_with_sqs.aws_sqs_dlq_url = None
    service = SQSService(settings_with_sqs)

    job = ProcessingJob(
        job_id="test-job-123",
        video_s3_key="uploads/video.mp4",
        video_s3_bucket="test-bucket",
    )

    service.send_to_dlq(job, "Test error")

    # Should not raise error, just log warning
    mock_sqs_client.send_message.assert_not_called()


def test_processing_job_serialization():
    """ProcessingJob should serialize/deserialize correctly."""
    job = ProcessingJob(
        job_id="test-123",
        video_s3_key="uploads/video.mp4",
        video_s3_bucket="test-bucket",
        status=JobStatus.PROCESSING,
        metadata={"key": "value"},
    )

    # Serialize
    json_str = job.to_json()
    assert isinstance(json_str, str)
    assert "test-123" in json_str

    # Deserialize
    job2 = ProcessingJob.from_json(json_str)
    assert job2.job_id == job.job_id
    assert job2.video_s3_key == job.video_s3_key
    assert job2.status == JobStatus.PROCESSING
    assert job2.metadata == job.metadata
