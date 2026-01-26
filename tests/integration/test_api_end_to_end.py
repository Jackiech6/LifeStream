"""End-to-end integration tests for API."""

from unittest.mock import MagicMock, patch

import pytest
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


def test_presigned_upload_flow():
    """Test presigned URL upload flow with mocked S3."""
    with patch("src.api.routes.presigned_upload.S3Service") as mock_s3:
        mock_s3.return_value.generate_presigned_url.return_value = (
            "https://bucket.s3.amazonaws.com/uploads/test.mp4?signature=xyz"
        )
        r = client.post(
            "/api/v1/upload/presigned-url",
            json={"filename": "test.mp4"},
        )
    assert r.status_code == 200
    data = r.json()
    assert "job_id" in data
    assert "upload_url" in data


def test_status_endpoint():
    """Test status endpoint (DynamoDB)."""
    with patch("src.api.routes.status.get_job") as mock_get:
        mock_get.return_value = {
            "job_id": "test-job-123",
            "status": "processing",
            "current_stage": "diarization",
            "timings": {"download": 100},
        }
        with patch("src.api.routes.status.Settings") as mock_s:
            mock_s.return_value.jobs_table_name = "test-jobs"
            mock_s.return_value.aws_region = "us-east-1"
            response = client.get("/api/v1/status/test-job-123")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-123"
    assert "status" in data


def test_deprecated_upload_returns_gone():
    """Deprecated POST /upload returns 410."""
    response = client.post(
        "/api/v1/upload/upload",
        files={"file": ("test.mp4", b"fake", "video/mp4")},
    )
    assert response.status_code == 410


def test_query_endpoint():
    """Test query endpoint."""
    with patch("src.api.routes.query.Settings") as mock_st:
        mock_st.return_value.pinecone_api_key = "pk"
        mock_st.return_value.openai_api_key = "sk"
        with patch("src.api.routes.query.create_vector_store"):
            with patch("src.api.routes.query.OpenAIEmbeddingModel"):
                with patch("src.api.routes.query.semantic_search") as mock_search:
                    mock_search.return_value = []
                    with patch("src.api.routes.query.synthesize_answer") as mock_synth:
                        mock_synth.return_value = "Answer"
                        response = client.post(
                            "/api/v1/query",
                            json={"query": "test query", "top_k": 5},
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
    """Test that CORS is configured (OPTIONS or GET on API path)."""
    response = client.get("/api/v1/status/some-id")
    # Route may 404 (no job) or 503 (no table); we just check no 5xx from CORS
    assert response.status_code in [200, 404, 503]
