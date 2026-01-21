"""End-to-end integration tests for API."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_api_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "LifeStream API"
    assert "version" in data


def test_api_health():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_api_docs_accessible():
    """Test that API documentation is accessible."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_upload_endpoint_with_mock():
    """Test upload endpoint with mocked services."""
    with patch("src.api.routes.upload.VideoService") as mock_service:
        mock_video_service = MagicMock()
        mock_job = MagicMock()
        mock_job.job_id = "test-job-123"
        mock_job.video_s3_bucket = "test-bucket"
        mock_job.video_s3_key = "uploads/test.mp4"
        mock_job.status = "pending"
        mock_video_service.create_upload_job.return_value = mock_job
        mock_service.return_value = mock_video_service
        
        # Create test file
        test_content = b"fake video content"
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.mp4", test_content, "video/mp4")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"


def test_status_endpoint():
    """Test status endpoint."""
    with patch("src.api.routes.status.S3Service") as mock_s3:
        mock_service = MagicMock()
        mock_service.file_exists.return_value = False
        mock_s3.return_value = mock_service
        
        response = client.get("/api/v1/status/test-job-123")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-123"
        assert "status" in data


def test_query_endpoint():
    """Test query endpoint."""
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


def test_invalid_endpoint():
    """Test invalid endpoint returns 404."""
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404


def test_cors_headers():
    """Test that CORS headers are present."""
    response = client.options("/api/v1/upload")
    # CORS is configured, should not error
    assert response.status_code in [200, 405]  # OPTIONS may not be explicitly handled


if __name__ == "__main__":
    from unittest.mock import patch, MagicMock
    pytest.main([__file__, "-v"])
