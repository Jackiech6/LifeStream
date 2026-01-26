"""Unit tests for API routes."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


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


def test_presigned_url_invalid_file_type():
    """Presigned-url should reject invalid file types."""
    response = client.post(
        "/api/v1/upload/presigned-url",
        json={"filename": "test.txt"},
    )
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_presigned_url_valid_file():
    """Presigned-url should accept valid video filename and return URL + job_id."""
    with patch("src.api.routes.presigned_upload.S3Service") as mock_s3:
        mock_s3.return_value.generate_presigned_url.return_value = (
            "https://bucket.s3.amazonaws.com/uploads/20260101_120000_test.mp4?signature=xyz"
        )
        response = client.post(
            "/api/v1/upload/presigned-url",
            json={"filename": "test.mp4"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert "upload_url" in data
    assert "s3_key" in data


def test_confirm_upload_empty_job_id():
    """Confirm should reject empty job_id."""
    response = client.post(
        "/api/v1/upload/confirm",
        json={"job_id": "", "s3_key": "uploads/fake.mp4"},
    )
    assert response.status_code == 400
    assert "job_id" in response.json()["detail"].lower()


def test_confirm_upload_empty_s3_key():
    """Confirm should reject empty s3_key."""
    response = client.post(
        "/api/v1/upload/confirm",
        json={"job_id": "j1", "s3_key": ""},
    )
    assert response.status_code == 400
    assert "s3_key" in response.json()["detail"].lower()


def test_confirm_upload_s3_key_must_start_with_uploads():
    """Confirm should reject s3_key not under uploads/."""
    response = client.post(
        "/api/v1/upload/confirm",
        json={"job_id": "j1", "s3_key": "other/key.mp4"},
    )
    assert response.status_code == 400
    assert "uploads" in response.json()["detail"].lower()


def test_confirm_upload_empty_file():
    """Confirm should reject when S3 file is empty."""
    with patch("src.api.routes.presigned_upload.S3Service") as mock_s3:
        mock_s3.return_value.file_exists.return_value = True
        mock_s3.return_value.get_file_metadata.return_value = {"size": 0}
        with patch("src.api.routes.presigned_upload.VideoService"):
            response = client.post(
                "/api/v1/upload/confirm",
                json={"job_id": "j1", "s3_key": "uploads/fake.mp4"},
            )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_deprecated_upload_returns_gone():
    """Deprecated POST /upload should return 410 Gone."""
    response = client.post(
        "/api/v1/upload/upload",
        files={"file": ("test.mp4", b"fake", "video/mp4")},
    )
    assert response.status_code == 410


def test_status_endpoint_not_found():
    """Status should return 404 when job not in DynamoDB."""
    with patch("src.api.routes.status.get_job") as mock_get:
        mock_get.return_value = None
        with patch("src.api.routes.status.Settings") as mock_s:
            mock_s.return_value.jobs_table_name = "test-jobs"
            mock_s.return_value.aws_region = "us-east-1"
            response = client.get("/api/v1/status/nonexistent-job")
    assert response.status_code == 404


def test_status_endpoint_completed():
    """Status should return completed when job is completed in DynamoDB."""
    with patch("src.api.routes.status.get_job") as mock_get:
        mock_get.return_value = {
            "job_id": "j1",
            "status": "completed",
            "current_stage": "completed",
            "created_at": "2026-01-20T12:00:00Z",
            "updated_at": "2026-01-20T12:05:00Z",
            "timings": {"download": 100, "upload": 200},
        }
        with patch("src.api.routes.status.Settings") as mock_s:
            mock_s.return_value.jobs_table_name = "test-jobs"
            mock_s.return_value.aws_region = "us-east-1"
            response = client.get("/api/v1/status/j1")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["progress"] == 1.0


def test_summary_endpoint_not_found():
    """Summary should return 404 when job not in DynamoDB."""
    with patch("src.api.routes.summary.get_job") as mock_get:
        mock_get.return_value = None
        with patch("src.api.routes.summary.Settings") as mock_s:
            mock_s.return_value.jobs_table_name = "test-jobs"
            mock_s.return_value.aws_region = "us-east-1"
            response = client.get("/api/v1/summary/nonexistent-job")
    assert response.status_code == 404


def test_summary_endpoint_json_format():
    """Summary should return JSON when job completed and result in S3."""
    summary_data = {
        "date": "2026-01-20",
        "video_source": "s3://bucket/video.mp4",
        "time_blocks": [],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(summary_data, tmp)
        tmp_path = tmp.name

    try:
        with patch("src.api.routes.summary.get_job") as mock_get:
            mock_get.return_value = {
                "job_id": "j1",
                "status": "completed",
                "result_s3_key": "results/j1/summary.json",
            }
            with patch("src.api.routes.summary.Settings") as mock_s:
                mock_s.return_value.jobs_table_name = "test-jobs"
                mock_s.return_value.aws_region = "us-east-1"
                mock_s.return_value.aws_s3_bucket_name = "b"
                with patch("src.api.routes.summary.S3Service") as mock_s3:
                    inst = MagicMock()
                    inst._bucket_name = "b"

                    def _download(key, path, bucket=None):
                        import shutil
                        shutil.copy(tmp_path, path)

                    inst.download_file.side_effect = _download
                    inst.file_exists.return_value = False
                    mock_s3.return_value = inst
                    with patch("src.api.routes.summary.LLMSummarizer") as mock_summarizer:
                        mock_summarizer.return_value.format_markdown_output.return_value = "# Summary\n\nTest"
                        response = client.get("/api/v1/summary/j1?format=json")
        assert response.status_code == 200, (response.json() if response.status_code != 200 else "")
        data = response.json()
        assert "job_id" in data
        assert "date" in data
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_query_endpoint():
    """Query endpoint should perform semantic search."""
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
    assert "answer" in data
    assert data["answer"] is not None


def test_query_endpoint_invalid_request():
    """Query endpoint should validate request."""
    response = client.post("/api/v1/query", json={"query": ""})
    assert response.status_code == 422


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


# --- Memory routes ---


def test_memory_list_503_when_not_pinecone():
    """GET /memory returns 503 when vector store is not Pinecone."""
    with patch("src.api.routes.memory.get_vector_store_type") as mock_type:
        mock_type.return_value = "faiss"
        response = client.get("/api/v1/memory")
    assert response.status_code == 503
    assert "Pinecone" in response.json()["detail"]


def test_memory_list_returns_jobs_and_chunks():
    """GET /memory returns jobs and chunks when Pinecone is configured."""
    with patch("src.api.routes.memory.get_vector_store_type") as mock_type:
        mock_type.return_value = "pinecone"
        with patch("src.api.routes.memory.Settings") as mock_s:
            mock_s.return_value.jobs_table_name = "test-jobs"
            mock_s.return_value.aws_region = "us-east-1"
            with patch("src.api.routes.memory.list_jobs") as mock_list_jobs:
                mock_list_jobs.return_value = [
                    {
                        "job_id": "j1",
                        "status": "completed",
                        "s3_key": "uploads/v.mp4",
                        "s3_bucket": "b1",
                        "created_at": "2026-01-20T10:00:00Z",
                    },
                ]
                with patch("src.api.routes.memory.create_vector_store") as mock_create:
                    mock_store = MagicMock()
                    mock_store.list_all_chunks.return_value = [
                        {
                            "id": "chunk_abc",
                            "video_id": "s3://b1/uploads/v.mp4",
                            "date": "2026-01-20",
                            "source_type": "summary_block",
                            "text": "Sample text",
                        },
                    ]
                    mock_create.return_value = mock_store
                    response = client.get("/api/v1/memory")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "chunks" in data
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["job_id"] == "j1"
    assert data["jobs"][0]["chunk_count"] == 1
    assert len(data["chunks"]) == 1
    assert data["chunks"][0]["id"] == "chunk_abc"


def test_memory_delete_chunks():
    """DELETE /memory/chunks deletes by IDs."""
    with patch("src.api.routes.memory.get_vector_store_type") as mock_type:
        mock_type.return_value = "pinecone"
        with patch("src.api.routes.memory.create_vector_store") as mock_create:
            mock_store = MagicMock()
            mock_create.return_value = mock_store
            response = client.request(
                "DELETE",
                "/api/v1/memory/chunks",
                json={"chunk_ids": ["chunk_1", "chunk_2"]},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] == 2
    assert set(data["chunk_ids"]) == {"chunk_1", "chunk_2"}
    mock_store.delete.assert_called_once()
    call_ids = mock_store.delete.call_args[0][0]
    assert set(call_ids) == {"chunk_1", "chunk_2"}


def test_memory_delete_chunks_503_when_not_pinecone():
    """DELETE /memory/chunks returns 503 when not Pinecone."""
    with patch("src.api.routes.memory.get_vector_store_type") as mock_type:
        mock_type.return_value = "faiss"
        response = client.request(
            "DELETE",
            "/api/v1/memory/chunks",
            json={"chunk_ids": ["chunk_1"]},
        )
    assert response.status_code == 503


def test_memory_delete_jobs():
    """DELETE /memory/jobs deletes job records and chunks by video_id."""
    with patch("src.api.routes.memory.get_vector_store_type") as mock_type:
        mock_type.return_value = "pinecone"
        with patch("src.api.routes.memory.Settings") as mock_s:
            mock_s.return_value.jobs_table_name = "test-jobs"
            mock_s.return_value.aws_region = "us-east-1"
            with patch("src.api.routes.memory.get_job") as mock_get_job:
                mock_get_job.return_value = {
                    "job_id": "j1",
                    "s3_key": "uploads/v.mp4",
                    "s3_bucket": "b1",
                }
                with patch("src.api.routes.memory.delete_job") as mock_delete_job:
                    mock_delete_job.return_value = True
                    with patch("src.api.routes.memory.create_vector_store") as mock_create:
                        mock_store = MagicMock()
                        mock_store.delete_by_filter = MagicMock()
                        mock_create.return_value = mock_store
                        response = client.request(
                            "DELETE",
                            "/api/v1/memory/jobs",
                            json={"job_ids": ["j1"]},
                        )
    assert response.status_code == 200
    data = response.json()
    assert data["deleted_jobs"] == 1
    assert "j1" in data["job_ids"]
    mock_store.delete_by_filter.assert_called_once()
    assert mock_store.delete_by_filter.call_args[0][0] == {"video_id": "s3://b1/uploads/v.mp4"}
