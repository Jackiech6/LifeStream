"""Unit tests for API routes."""

import pytest
import json
import tempfile
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


@pytest.fixture
def mock_settings():
    """Mock settings."""
    with patch("src.api.routes.upload.Settings") as mock:
        settings = MagicMock()
        settings.aws_s3_bucket_name = "test-bucket"
        settings.aws_sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        settings.aws_region = "us-east-1"
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_video_service():
    """Mock video service."""
    with patch("src.api.routes.upload.VideoService") as mock:
        service = MagicMock()
        job = MagicMock()
        job.job_id = "test-job-123"
        job.video_s3_bucket = "test-bucket"
        job.video_s3_key = "uploads/test-video.mp4"
        service.create_upload_job.return_value = job
        mock.return_value = service
        yield service


def test_root_endpoint():
    """Root endpoint should return API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "LifeStream API"
    assert "version" in data


def test_health_endpoint():
    """Health endpoint should return healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_upload_endpoint_valid_file(mock_settings, mock_video_service):
    """Upload endpoint should accept valid video file."""
    # Create a test video file
    test_content = b"fake video content"
    
    response = client.post(
        "/api/v1/upload",
        files={"file": ("test.mp4", test_content, "video/mp4")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"


def test_upload_endpoint_invalid_file_type():
    """Upload endpoint should reject invalid file types."""
    test_content = b"not a video"
    
    response = client.post(
        "/api/v1/upload",
        files={"file": ("test.txt", test_content, "text/plain")}
    )
    
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_upload_endpoint_empty_file():
    """Upload endpoint should reject empty files."""
    test_content = b""
    
    response = client.post(
        "/api/v1/upload",
        files={"file": ("test.mp4", test_content, "video/mp4")}
    )
    
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_status_endpoint_not_found():
    """Status endpoint should handle missing jobs."""
    with patch("src.api.routes.status.S3Service") as mock_s3:
        mock_service = MagicMock()
        mock_service.file_exists.return_value = False
        mock_s3.return_value = mock_service
        
        response = client.get("/api/v1/status/nonexistent-job")
        
        assert response.status_code == 200  # Returns queued status
        data = response.json()
        assert data["status"] == "queued"


def test_status_endpoint_completed():
    """Status endpoint should return completed status."""
    with patch("src.api.routes.status.S3Service") as mock_s3:
        mock_service = MagicMock()
        mock_service.file_exists.side_effect = lambda key: "summary.json" in key or "summary.md" in key
        mock_service.get_file_metadata.return_value = {}
        mock_s3.return_value = mock_service
        
        response = client.get("/api/v1/status/completed-job")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["progress"] == 1.0


def test_summary_endpoint_not_found():
    """Summary endpoint should return 404 for missing jobs."""
    with patch("src.api.routes.summary.S3Service") as mock_s3:
        mock_service = MagicMock()
        mock_service.file_exists.return_value = False
        mock_s3.return_value = mock_service
        
        response = client.get("/api/v1/summary/nonexistent-job")
        
        assert response.status_code == 404


def test_summary_endpoint_json_format():
    """Summary endpoint should return JSON format."""
    with patch("src.api.routes.summary.S3Service") as mock_s3:
        from src.models.data_models import DailySummary, TimeBlock
        
        mock_service = MagicMock()
        mock_service.file_exists.return_value = True
        
        # Mock download
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            summary_data = {
                "date": "2026-01-20",
                "video_source": "s3://bucket/video.mp4",
                "time_blocks": []
            }
            json.dump(summary_data, tmp)
            tmp_path = tmp.name
        
        def mock_download(key, path):
            import shutil
            shutil.copy(tmp_path, path)
        
        mock_service.download_file.side_effect = mock_download
        mock_s3.return_value = mock_service
        
        with patch("src.api.routes.summary.LLMSummarizer") as mock_summarizer:
            mock_summarizer_instance = MagicMock()
            mock_summarizer_instance.format_markdown_output.return_value = "# Summary\n\nTest"
            mock_summarizer.return_value = mock_summarizer_instance
            
            response = client.get("/api/v1/summary/test-job?format=json")
            
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            assert "date" in data
        
        Path(tmp_path).unlink(missing_ok=True)


def test_query_endpoint():
    """Query endpoint should perform semantic search."""
    with patch("src.api.routes.query.create_vector_store") as mock_store:
        with patch("src.api.routes.query.OpenAIEmbeddingModel") as mock_embedder:
            with patch("src.api.routes.query.semantic_search") as mock_search:
                mock_search.return_value = []
                
                response = client.post(
                    "/api/v1/query",
                    json={
                        "query": "test query",
                        "top_k": 5
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "query" in data
                assert "results" in data


def test_query_endpoint_invalid_request():
    """Query endpoint should validate request."""
    response = client.post(
        "/api/v1/query",
        json={
            "query": ""  # Empty query
        }
    )
    
    assert response.status_code == 422  # Validation error


def test_api_docs_accessible():
    """API documentation should be accessible."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_schema_accessible():
    """OpenAPI schema should be accessible."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "paths" in schema
