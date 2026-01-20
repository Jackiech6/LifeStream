"""Integration tests for S3 service.

These tests require AWS credentials and an S3 bucket to be configured.
They will be skipped if credentials are not available.
"""

import os
import tempfile
from pathlib import Path

import pytest

from src.storage.s3_service import S3Service
from config.settings import Settings


@pytest.fixture
def s3_settings():
    """Create settings for S3 integration tests."""
    settings = Settings()
    
    # Get bucket name from environment or use test bucket
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME") or os.getenv("TEST_S3_BUCKET")
    if not bucket_name:
        pytest.skip("AWS_S3_BUCKET_NAME or TEST_S3_BUCKET not set")
    
    settings.aws_s3_bucket_name = bucket_name
    settings.aws_region = os.getenv("AWS_REGION", "us-east-1")
    settings.aws_profile = os.getenv("AWS_PROFILE")
    
    return settings


@pytest.fixture
def test_file():
    """Create a temporary test file."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(b"test video content for integration test")
        yield tmp.name
    Path(tmp.name).unlink(missing_ok=True)


@pytest.mark.integration
def test_s3_upload_and_download(s3_settings, test_file):
    """Test uploading and downloading a file from S3."""
    service = S3Service(s3_settings)
    
    # Upload file
    s3_key = f"test-uploads/integration-test-{os.getpid()}.mp4"
    upload_result = service.upload_file(test_file, s3_key)
    
    assert upload_result.success is True
    assert upload_result.bucket == s3_settings.aws_s3_bucket_name
    assert upload_result.key == s3_key
    
    # Verify file exists
    assert service.file_exists(s3_key) is True
    
    # Download file
    with tempfile.TemporaryDirectory() as tmpdir:
        download_path = Path(tmpdir) / "downloaded.mp4"
        download_success = service.download_file(s3_key, download_path)
        
        assert download_success is True
        assert download_path.exists()
        
        # Verify content matches
        original_content = Path(test_file).read_bytes()
        downloaded_content = download_path.read_bytes()
        assert original_content == downloaded_content
    
    # Cleanup
    service.delete_file(s3_key)


@pytest.mark.integration
def test_s3_presigned_url(s3_settings):
    """Test generating presigned URLs."""
    service = S3Service(s3_settings)
    
    s3_key = f"test-uploads/presigned-test-{os.getpid()}.mp4"
    url = service.generate_presigned_url(s3_key, expiration=3600, http_method="PUT")
    
    assert url.startswith("https://")
    assert s3_settings.aws_s3_bucket_name in url
    assert s3_key in url


@pytest.mark.integration
def test_s3_file_metadata(s3_settings, test_file):
    """Test retrieving file metadata."""
    service = S3Service(s3_settings)
    
    s3_key = f"test-uploads/metadata-test-{os.getpid()}.mp4"
    upload_result = service.upload_file(test_file, s3_key)
    
    assert upload_result.success is True
    
    # Get metadata
    metadata = service.get_file_metadata(s3_key)
    
    assert metadata is not None
    assert metadata["size"] == Path(test_file).stat().st_size
    assert metadata["etag"] is not None
    
    # Cleanup
    service.delete_file(s3_key)


@pytest.mark.integration
def test_s3_list_files(s3_settings, test_file):
    """Test listing files in S3."""
    service = S3Service(s3_settings)
    
    # Upload a test file
    s3_key = f"test-uploads/list-test-{os.getpid()}.mp4"
    upload_result = service.upload_file(test_file, s3_key)
    assert upload_result.success is True
    
    # List files with prefix
    files = service.list_files(prefix="test-uploads/")
    
    # Should find at least our uploaded file
    keys = [f["key"] for f in files]
    assert s3_key in keys
    
    # Cleanup
    service.delete_file(s3_key)
