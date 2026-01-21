"""Unit tests for Lambda handler."""

from unittest.mock import MagicMock, patch, Mock
import json
import pytest
import tempfile
from pathlib import Path

from src.workers.lambda_handler import lambda_handler, process_video_from_s3, process_video_job
from src.messaging.sqs_service import ProcessingJob, JobStatus
from config.settings import Settings


@pytest.fixture
def mock_s3_service():
    """Create a mocked S3 service."""
    with patch("src.workers.lambda_handler.S3Service") as mock_s3:
        mock_service = MagicMock()
        mock_s3.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_sqs_service():
    """Create a mocked SQS service."""
    with patch("src.workers.lambda_handler.SQSService") as mock_sqs:
        mock_service = MagicMock()
        mock_sqs.return_value = mock_service
        yield mock_service


@pytest.fixture
def sample_sqs_event():
    """Create a sample SQS event."""
    job = ProcessingJob(
        job_id="test-job-123",
        video_s3_key="uploads/video.mp4",
        video_s3_bucket="test-bucket",
    )

    return {
        "Records": [
            {
                "body": job.to_json(),
                "messageAttributes": {
                    "job_id": {"stringValue": job.job_id},
                },
            }
        ]
    }


def test_lambda_handler_sqs_event(sample_sqs_event, mock_s3_service, mock_sqs_service):
    """lambda_handler should process SQS events."""
    # Mock video download
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"fake video data")

    mock_s3_service.download_file.return_value = Path(tmp_path)
    mock_s3_service.bucket_name = "test-bucket"

    # Mock process_video to return a summary
    with patch("src.workers.lambda_handler.process_video") as mock_process:
        from src.models.data_models import DailySummary, TimeBlock

        mock_summary = DailySummary(
            date="2026-01-20",
            video_source="s3://test-bucket/uploads/video.mp4",
            time_blocks=[TimeBlock(start_time="10:00", end_time="11:00", activity="Test")],
        )
        mock_process.return_value = mock_summary

        # Mock file operations
        with patch("pathlib.Path.write_text") as mock_write:
            with patch("pathlib.Path.read_text", return_value="test content"):
                result = lambda_handler(sample_sqs_event, None)

                assert result["statusCode"] == 200
                assert "results" in result
                assert len(result["results"]) == 1

    # Cleanup
    Path(tmp_path).unlink(missing_ok=True)


def test_lambda_handler_direct_invocation(mock_s3_service):
    """lambda_handler should handle direct invocation."""
    event = {
        "job_id": "test-job-123",
        "video_s3_key": "uploads/video.mp4",
        "video_s3_bucket": "test-bucket",
    }

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"fake video data")

    mock_s3_service.download_file.return_value = Path(tmp_path)
    mock_s3_service.bucket_name = "test-bucket"

    # Mock settings with SQS URL
    with patch("src.workers.lambda_handler.Settings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.aws_sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        mock_settings.aws_sqs_dlq_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-dlq"
        mock_settings.aws_s3_bucket_name = "test-bucket"
        mock_settings.aws_region = "us-east-1"

        with patch("src.workers.lambda_handler.process_video") as mock_process:
            from src.models.data_models import DailySummary, TimeBlock

            mock_summary = DailySummary(
                date="2026-01-20",
                video_source="s3://test-bucket/uploads/video.mp4",
                time_blocks=[],
            )
            mock_process.return_value = mock_summary

            with patch("pathlib.Path.write_text"):
                with patch("pathlib.Path.read_text", return_value="test"):
                    result = lambda_handler(event, None)

                    assert result["statusCode"] == 200

    Path(tmp_path).unlink(missing_ok=True)


def test_lambda_handler_error_handling(mock_s3_service, mock_sqs_service):
    """lambda_handler should handle errors gracefully."""
    event = {
        "job_id": "test-job-123",
        "video_s3_key": "uploads/video.mp4",
        "video_s3_bucket": "test-bucket",
    }

    mock_s3_service.download_file.side_effect = Exception("Download failed")

    result = lambda_handler(event, None)

    assert result["statusCode"] == 500
    assert "error" in result


def test_process_video_job_sends_to_dlq_on_failure():
    """process_video_job should send failed jobs to DLQ without import errors."""
    from src.messaging.sqs_service import ProcessingJob

    job = ProcessingJob(
        job_id="job-dlq-1",
        video_s3_key="uploads/video.mp4",
        video_s3_bucket="test-bucket",
    )
    settings = Settings()
    settings.aws_sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
    settings.aws_sqs_dlq_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-dlq"
    settings.aws_region = "us-east-1"

    with patch("src.workers.lambda_handler.S3Service") as mock_s3, \
         patch("src.workers.lambda_handler.process_video_from_s3") as mock_proc, \
         patch("src.messaging.sqs_service.SQSService.send_to_dlq") as mock_send_to_dlq:

        # Force processing to fail
        mock_proc.side_effect = Exception("processing failed")

        result = process_video_job(job, settings)

        assert result["statusCode"] == 500
        mock_send_to_dlq.assert_called_once()


def test_process_video_from_s3(mock_s3_service):
    """process_video_from_s3 should process video downloaded from S3."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"fake video data")

    mock_s3_service.bucket_name = "test-bucket"

    with patch("src.workers.lambda_handler.process_video") as mock_process:
        from src.models.data_models import DailySummary, TimeBlock

        mock_summary = DailySummary(
            date="2026-01-20",
            video_source="local_path",
            time_blocks=[],
        )
        mock_process.return_value = mock_summary

        summary = process_video_from_s3(
            s3_bucket="test-bucket",
            s3_key="uploads/video.mp4",
            local_video_path=tmp_path,
        )

        assert summary.video_source == "s3://test-bucket/uploads/video.mp4"
        mock_process.assert_called_once()

    Path(tmp_path).unlink(missing_ok=True)
