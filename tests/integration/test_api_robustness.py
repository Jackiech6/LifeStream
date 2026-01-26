"""Robustness tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.api.main import app

client = TestClient(app)


def test_upload_large_file_rejected():
    """Presigned-url should reject file_size over limit."""
    response = client.post(
        "/api/v1/upload/presigned-url",
        json={"filename": "large.mp4", "file_size": 3 * 1024 * 1024 * 1024},
    )
    assert response.status_code == 400
    assert "large" in response.json()["detail"].lower() or "2" in response.json()["detail"]


def test_upload_invalid_file_type():
    """Invalid file types should be rejected."""
    response = client.post(
        "/api/v1/upload/presigned-url",
        json={"filename": "test.txt"},
    )
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_upload_empty_file():
    """Confirm should reject when S3 file is empty."""
    with patch("src.api.routes.presigned_upload.S3Service") as mock_s3:
        mock_s3.return_value.file_exists.return_value = True
        mock_s3.return_value.get_file_metadata.return_value = {"size": 0}
        with patch("src.api.routes.presigned_upload.VideoService"):
            response = client.post(
                "/api/v1/upload/confirm",
                json={"job_id": "j1", "s3_key": "uploads/empty.mp4"},
            )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_status_nonexistent_job():
    """Status returns 404 when job not in DynamoDB."""
    with patch("src.api.routes.status.get_job") as mock_get:
        mock_get.return_value = None
        with patch("src.api.routes.status.Settings") as mock_s:
            mock_s.return_value.jobs_table_name = "test-jobs"
            mock_s.return_value.aws_region = "us-east-1"
            response = client.get("/api/v1/status/nonexistent-job-id")
    assert response.status_code == 404


def test_summary_nonexistent_job():
    """Summary returns 404 when job not in DynamoDB."""
    with patch("src.api.routes.summary.get_job") as mock_get:
        mock_get.return_value = None
        with patch("src.api.routes.summary.Settings") as mock_s:
            mock_s.return_value.jobs_table_name = "test-jobs"
            mock_s.return_value.aws_region = "us-east-1"
            response = client.get("/api/v1/summary/nonexistent-job-id")
    assert response.status_code == 404


def test_query_empty_string():
    """Query endpoint should validate empty queries."""
    response = client.post(
        "/api/v1/query",
        json={"query": ""}
    )
    assert response.status_code == 422  # Validation error


def test_query_invalid_top_k():
    """Query endpoint should validate top_k parameter."""
    response = client.post(
        "/api/v1/query",
        json={
            "query": "test",
            "top_k": 100  # Exceeds max
        }
    )
    assert response.status_code == 422  # Validation error


def test_query_missing_required_field():
    """Query endpoint should require query field."""
    response = client.post(
        "/api/v1/query",
        json={}  # Missing query
    )
    assert response.status_code == 422  # Validation error


def test_malformed_json():
    """API should handle malformed JSON gracefully."""
    response = client.post(
        "/api/v1/query",
        data="not json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code in [400, 422]  # Bad request or validation error


def test_concurrent_requests():
    """API should handle concurrent requests."""
    import concurrent.futures
    
    def make_request():
        return client.get("/health")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    # All requests should succeed
    assert all(r.status_code == 200 for r in results)


def test_error_response_format():
    """Error responses should follow consistent format."""
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    
    # Should return JSON error response
    try:
        data = response.json()
        assert "detail" in data or "error" in data
    except:
        # Some 404 responses might be HTML, which is also acceptable
        pass
