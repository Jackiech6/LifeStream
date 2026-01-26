"""
E2E integration test: DynamoDB status, S3 outputs, and Pinecone indexing.

Uses TestClient with mocked DynamoDB (get_job), S3 (download), and search/synthesis
to verify the API reads status from DynamoDB, summary from S3, and query path
uses retrieval + synthesis (Pinecone indexing implied by query flow).
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

JOB_ID = "e2e-test-job-123"
S3_KEY = "uploads/20260120_120000_e2e_test.mp4"
RESULT_KEY = "results/e2e-test-job-123/summary.json"


@pytest.fixture
def mock_job_completed():
    """Simulate a completed job in DynamoDB."""
    return {
        "job_id": JOB_ID,
        "status": "completed",
        "current_stage": "completed",
        "s3_key": S3_KEY,
        "s3_bucket": "test-bucket",
        "result_s3_key": RESULT_KEY,
        "created_at": "2026-01-20T12:00:00Z",
        "updated_at": "2026-01-20T12:05:00Z",
        "timings": {"download": 100, "audio_extraction": 200, "diarization": 500, "asr": 1000},
    }


@pytest.fixture
def mock_summary_json():
    """Minimal DailySummary-like JSON for S3."""
    return {
        "date": "2026-01-20",
        "video_source": f"s3://test-bucket/{S3_KEY}",
        "time_blocks": [],
        "video_metadata": None,
    }


def test_e2e_dynamodb_status_s3_summary_pinecone_query(
    mock_job_completed,
    mock_summary_json,
):
    """
    E2E: GET status (DynamoDB) -> GET summary (S3) -> POST query (Pinecone + synthesis).
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(mock_summary_json, tmp)
        tmp_path = tmp.name

    try:
        with patch("src.api.routes.status.get_job") as mock_get_job:
            with patch("src.api.routes.status.Settings") as mock_st:
                mock_st.return_value.jobs_table_name = "test-jobs"
                mock_st.return_value.aws_region = "us-east-1"
                mock_get_job.return_value = mock_job_completed

                status_resp = client.get(f"/api/v1/status/{JOB_ID}")
                assert status_resp.status_code == 200
                data = status_resp.json()
                assert data["job_id"] == JOB_ID
                assert data["status"] == "completed"
                assert data["progress"] == 1.0
                assert data["current_stage"] == "completed"
                assert "timings" in data
                assert data["timings"] == mock_job_completed["timings"]

        with patch("src.api.routes.summary.get_job") as mock_get_job:
            mock_get_job.return_value = mock_job_completed
            with patch("src.api.routes.summary.Settings") as mock_st:
                mock_st.return_value.jobs_table_name = "test-jobs"
                mock_st.return_value.aws_region = "us-east-1"
                mock_st.return_value.aws_s3_bucket_name = "test-bucket"
                with patch("src.api.routes.summary.S3Service") as mock_s3:
                    inst = MagicMock()
                    inst._bucket_name = "test-bucket"

                    def _download(key, path, bucket=None):
                        import shutil
                        shutil.copy(tmp_path, path)

                    inst.download_file.side_effect = _download
                    inst.file_exists.return_value = False
                    mock_s3.return_value = inst
                    with patch("src.api.routes.summary.LLMSummarizer") as mock_llm:
                        mock_llm.return_value.format_markdown_output.return_value = "# Summary\n\nE2E test."

                        summary_resp = client.get(f"/api/v1/summary/{JOB_ID}?format=json")
                        assert summary_resp.status_code == 200
                        summary_data = summary_resp.json()
                        assert summary_data["job_id"] == JOB_ID
                        assert summary_data["date"] == mock_summary_json["date"]
                        assert "summary_markdown" in summary_data

        with patch("src.api.routes.query.Settings") as mock_st:
            mock_st.return_value.pinecone_api_key = "pk"
            mock_st.return_value.openai_api_key = "sk"
            with patch("src.api.routes.query.create_vector_store"):
                with patch("src.api.routes.query.OpenAIEmbeddingModel"):
                    with patch("src.api.routes.query.semantic_search") as mock_search:
                        from src.search.semantic_search import SearchResult
                        mock_search.return_value = [
                            SearchResult(
                                chunk_id="c1",
                                text="E2E test chunk",
                                score=0.9,
                                metadata={"job_id": JOB_ID},
                            ),
                        ]
                        with patch("src.api.routes.query.synthesize_answer") as mock_synth:
                            mock_synth.return_value = "Synthesized answer from Pinecone chunks."

                            query_resp = client.post(
                                "/api/v1/query",
                                json={"query": "What happened in the E2E test?", "top_k": 5},
                            )
                            assert query_resp.status_code == 200
                            query_data = query_resp.json()
                            assert "answer" in query_data
                            assert "Synthesized answer" in query_data["answer"]
                            assert query_data["total_results"] == 1
    finally:
        Path(tmp_path).unlink(missing_ok=True)
