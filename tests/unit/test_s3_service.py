"""Unit tests for S3Service."""

from unittest.mock import MagicMock, patch, Mock
from pathlib import Path
import tempfile

import pytest

from src.storage.s3_service import S3Service, S3UploadResult
from config.settings import Settings


@pytest.fixture
def mock_s3_client():
    """Create a mocked S3 client."""
    with patch("boto3.client") as mock_client_func, \
         patch("boto3.Session") as mock_session_class:
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session
        mock_client_func.return_value = mock_client
        yield mock_client


@pytest.fixture
def settings_with_bucket():
    """Create settings with S3 bucket configured."""
    settings = Settings()
    settings.aws_s3_bucket_name = "test-bucket"
    settings.aws_region = "us-east-1"
    return settings


def test_s3_service_initialization(settings_with_bucket, mock_s3_client):
    """S3Service should initialize with correct bucket name."""
    service = S3Service(settings_with_bucket)
    assert service._bucket_name == "test-bucket"
    assert service.client == mock_s3_client


def test_s3_service_missing_bucket_name():
    """S3Service should raise error if bucket name not configured."""
    settings = Settings()
    settings.aws_s3_bucket_name = None

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="S3 bucket name not configured"):
            S3Service(settings)


def test_upload_file_success(settings_with_bucket, mock_s3_client):
    """upload_file should successfully upload a file."""
    # Create a temporary test file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(b"test video content")
        tmp_path = tmp.name

    try:
        mock_s3_client.head_object.return_value = {"ETag": '"abc123"'}
        service = S3Service(settings_with_bucket)

        result = service.upload_file(tmp_path, "uploads/test.mp4")

        assert result.success is True
        assert result.bucket == "test-bucket"
        assert result.key == "uploads/test.mp4"
        assert result.s3_path == "s3://test-bucket/uploads/test.mp4"
        assert result.etag == "abc123"
        assert result.error is None

        # Verify upload_file was called
        mock_s3_client.upload_file.assert_called_once()
        call_args = mock_s3_client.upload_file.call_args
        assert call_args[0][0] == tmp_path
        assert call_args[0][1] == "test-bucket"
        assert call_args[0][2] == "uploads/test.mp4"

    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_upload_file_not_found(settings_with_bucket, mock_s3_client):
    """upload_file should raise FileNotFoundError for missing file."""
    service = S3Service(settings_with_bucket)

    with pytest.raises(FileNotFoundError):
        service.upload_file("/nonexistent/file.mp4", "uploads/test.mp4")


def test_upload_file_failure(settings_with_bucket, mock_s3_client):
    """upload_file should return failure result on error."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"test")
        tmp_path = tmp.name

    try:
        from botocore.exceptions import ClientError

        mock_s3_client.upload_file.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "UploadObject"
        )

        service = S3Service(settings_with_bucket)
        result = service.upload_file(tmp_path, "uploads/test.mp4")

        assert result.success is False
        assert result.error is not None
        assert "AccessDenied" in result.error or "S3 upload failed" in result.error

    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_download_file_success(settings_with_bucket, mock_s3_client):
    """download_file should successfully download a file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = Path(tmpdir) / "downloaded.mp4"
        
        # Create the file after download_file is called (simulate boto3 behavior)
        def create_file_side_effect(*args, **kwargs):
            Path(local_path).write_bytes(b"downloaded content")
        
        mock_s3_client.download_file.side_effect = create_file_side_effect

        service = S3Service(settings_with_bucket)
        result = service.download_file("uploads/test.mp4", local_path)

        assert result is True
        assert local_path.exists()

        # Verify download_file was called
        mock_s3_client.download_file.assert_called_once_with(
            "test-bucket",
            "uploads/test.mp4",
            str(local_path),
        )


def test_download_file_failure(settings_with_bucket, mock_s3_client):
    """download_file should raise RuntimeError on failure."""
    from botocore.exceptions import ClientError

    mock_s3_client.download_file.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}}, "GetObject"
    )

    service = S3Service(settings_with_bucket)

    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = Path(tmpdir) / "downloaded.mp4"
        with pytest.raises(RuntimeError, match="S3 download failed"):
            service.download_file("uploads/nonexistent.mp4", local_path)


def test_generate_presigned_url(settings_with_bucket, mock_s3_client):
    """generate_presigned_url should return a valid URL."""
    mock_s3_client.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-bucket/uploads/test.mp4?signature=abc123"

    service = S3Service(settings_with_bucket)
    url = service.generate_presigned_url("uploads/test.mp4", expiration=3600)

    assert url.startswith("https://")
    assert "test-bucket" in url
    assert "uploads/test.mp4" in url

    mock_s3_client.generate_presigned_url.assert_called_once()


def test_delete_file(settings_with_bucket, mock_s3_client):
    """delete_file should successfully delete a file."""
    service = S3Service(settings_with_bucket)
    result = service.delete_file("uploads/test.mp4")

    assert result is True
    mock_s3_client.delete_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="uploads/test.mp4",
    )


def test_file_exists(settings_with_bucket, mock_s3_client):
    """file_exists should return True for existing files."""
    service = S3Service(settings_with_bucket)
    result = service.file_exists("uploads/test.mp4")

    assert result is True
    mock_s3_client.head_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="uploads/test.mp4",
    )


def test_file_not_exists(settings_with_bucket, mock_s3_client):
    """file_exists should return False for non-existent files."""
    from botocore.exceptions import ClientError

    mock_s3_client.head_object.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "HeadObject"
    )

    service = S3Service(settings_with_bucket)
    result = service.file_exists("uploads/nonexistent.mp4")

    assert result is False


def test_get_file_metadata(settings_with_bucket, mock_s3_client):
    """get_file_metadata should return file metadata."""
    mock_s3_client.head_object.return_value = {
        "ContentLength": 1024,
        "LastModified": "2026-01-20T12:00:00Z",
        "ETag": '"abc123"',
        "ContentType": "video/mp4",
        "Metadata": {"custom": "value"},
    }

    service = S3Service(settings_with_bucket)
    metadata = service.get_file_metadata("uploads/test.mp4")

    assert metadata is not None
    assert metadata["size"] == 1024
    assert metadata["etag"] == "abc123"
    assert metadata["content_type"] == "video/mp4"
    assert metadata["metadata"]["custom"] == "value"


def test_list_files(settings_with_bucket, mock_s3_client):
    """list_files should return list of files."""
    mock_s3_client.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "uploads/video1.mp4",
                "Size": 1024,
                "LastModified": "2026-01-20T12:00:00Z",
                "ETag": '"etag1"',
            },
            {
                "Key": "uploads/video2.mp4",
                "Size": 2048,
                "LastModified": "2026-01-20T13:00:00Z",
                "ETag": '"etag2"',
            },
        ]
    }

    service = S3Service(settings_with_bucket)
    files = service.list_files(prefix="uploads/")

    assert len(files) == 2
    assert files[0]["key"] == "uploads/video1.mp4"
    assert files[0]["size"] == 1024
    assert files[1]["key"] == "uploads/video2.mp4"
    assert files[1]["size"] == 2048
