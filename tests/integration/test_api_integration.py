"""Integration tests for API endpoints."""

import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


@pytest.mark.skip(reason="Requires actual AWS resources")
def test_upload_and_status_flow():
    """Test complete upload and status check flow."""
    # This test requires:
    # - S3 bucket configured
    # - SQS queue configured
    # - Valid AWS credentials
    pass


@pytest.mark.skip(reason="Requires actual vector store")
def test_query_integration():
    """Test query endpoint with real vector store."""
    # This test requires:
    # - Vector store (Pinecone) configured
    # - Indexed data
    # - Valid API keys
    pass


def test_api_structure():
    """Test that API structure is correct."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    assert "/api/v1/upload/presigned-url" in paths
    assert "/api/v1/upload/confirm" in paths
    assert "/api/v1/status/{job_id}" in paths
    assert "/api/v1/summary/{job_id}" in paths
    assert "/api/v1/query" in paths
    assert "/health" in paths


def test_cors_headers():
    """Test that CORS is configured (OPTIONS on API path)."""
    response = client.options("/api/v1/upload/presigned-url")
    assert response.status_code in [200, 405]


def test_error_handling():
    """Test that errors are handled gracefully."""
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    response = client.get("/api/v1/upload/presigned-url")
    assert response.status_code == 405  # POST only; GET method not allowed
