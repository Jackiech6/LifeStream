"""Integration tests for event-driven processing pipeline (Stage 3.2)."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.queue.sqs_service import SQSService, ProcessingJob, JobStatus
from src.services.video_service import VideoService
from src.storage.s3_service import S3Service
from config.settings import Settings


@pytest.fixture
def settings_with_aws():
    """Create settings with AWS configuration."""
    settings = Settings()
    settings.aws_s3_bucket_name = "test-bucket"
    settings.aws_sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
    settings.aws_sqs_dlq_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-dlq"
    settings.aws_region = "us-east-1"
    return settings


def test_video_service_create_upload_job(settings_with_aws):
    """VideoService should create and enqueue processing job."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"fake video data")

    try:
        with patch("src.services.video_service.S3Service") as mock_s3_class:
            with patch("src.services.video_service.SQSService") as mock_sqs_class:
                mock_s3 = MagicMock()
                mock_s3.bucket_name = "test-bucket"
                mock_s3_class.return_value = mock_s3

                mock_sqs = MagicMock()
                mock_sqs_class.return_value = mock_sqs

                service = VideoService(settings_with_aws)
                job = service.create_upload_job(tmp_path)

                assert job.job_id is not None
                assert job.video_s3_key.startswith("uploads/")
                assert job.status == JobStatus.PENDING
                mock_s3.upload_file.assert_called_once()
                mock_sqs.send_processing_job.assert_called_once()

    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_video_service_generate_presigned_url(settings_with_aws):
    """VideoService should generate presigned upload URL."""
    with patch("src.services.video_service.S3Service") as mock_s3_class:
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-bucket/uploads/video.mp4?signature=..."
        mock_s3_class.return_value = mock_s3

        service = VideoService(settings_with_aws)
        result = service.generate_presigned_upload_url("test-video.mp4")

        assert "url" in result
        assert "s3_key" in result
        assert result["s3_key"].startswith("uploads/")
        mock_s3.generate_presigned_url.assert_called_once()


def test_sqs_service_integration_flow(settings_with_aws):
    """Test complete SQS flow: send, receive, delete."""
    with patch("src.queue.sqs_service.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Mock send
        mock_client.send_message.return_value = {"MessageId": "msg-123"}

        # Mock receive
        job = ProcessingJob(
            job_id="test-job-123",
            video_s3_key="uploads/video.mp4",
            video_s3_bucket="test-bucket",
        )
        mock_client.receive_message.return_value = {
            "Messages": [
                {
                    "Body": job.to_json(),
                    "ReceiptHandle": "receipt-123",
                    "MessageId": "msg-123",
                }
            ]
        }

        service = SQSService(settings_with_aws)

        # Send job
        message_id = service.send_processing_job(job)
        assert message_id == "msg-123"

        # Receive job
        jobs = service.receive_job()
        assert len(jobs) == 1
        assert jobs[0].job_id == "test-job-123"

        # Delete job
        service.delete_job(jobs[0])
        mock_client.delete_message.assert_called_once()


def test_processing_job_serialization_roundtrip():
    """ProcessingJob should serialize and deserialize correctly."""
    original = ProcessingJob(
        job_id="test-123",
        video_s3_key="uploads/video.mp4",
        video_s3_bucket="test-bucket",
        status=JobStatus.PROCESSING,
        metadata={"key": "value"},
    )

    # Serialize
    json_str = original.to_json()
    assert isinstance(json_str, str)

    # Deserialize
    restored = ProcessingJob.from_json(json_str)

    assert restored.job_id == original.job_id
    assert restored.video_s3_key == original.video_s3_key
    assert restored.status == original.status
    assert restored.metadata == original.metadata


@pytest.mark.skip(reason="Requires actual AWS credentials and resources")
def test_end_to_end_processing_flow():
    """End-to-end test: upload video, enqueue job, process."""
    # This test requires:
    # - AWS credentials configured
    # - S3 bucket created
    # - SQS queue created
    # - Lambda function deployed
    pass
