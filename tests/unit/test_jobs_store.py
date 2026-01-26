"""Unit tests for jobs_store."""

import pytest
from unittest.mock import patch, MagicMock

from src.utils import jobs_store


def test_list_jobs_empty_table():
    """list_jobs returns [] when table_name is empty."""
    result = jobs_store.list_jobs(table_name="", region="us-east-1")
    assert result == []


def test_list_jobs_scan_called_with_filter():
    """list_jobs uses FilterExpression when status_filter is set."""
    mock_dynamo = MagicMock()
    mock_dynamo.scan.return_value = {"Items": []}
    with patch("boto3.client", return_value=mock_dynamo):
        jobs_store.list_jobs(
            table_name="test-jobs",
            region="us-east-1",
            status_filter="completed",
            limit=100,
        )
        call_kw = mock_dynamo.scan.call_args[1]
        assert call_kw["TableName"] == "test-jobs"
        assert call_kw["FilterExpression"] == "#st = :st"
        assert call_kw["ExpressionAttributeNames"] == {"#st": "status"}
        assert call_kw["ExpressionAttributeValues"] == {":st": {"S": "completed"}}
        assert call_kw["Limit"] == 100


def test_list_jobs_parse_items():
    """list_jobs parses DynamoDB items into job dicts."""
    mock_dynamo = MagicMock()
    mock_dynamo.scan.return_value = {
        "Items": [
            {
                "job_id": {"S": "j1"},
                "status": {"S": "completed"},
                "s3_key": {"S": "uploads/v.mp4"},
                "s3_bucket": {"S": "b1"},
                "created_at": {"S": "2026-01-20T10:00:00Z"},
                "updated_at": {"S": "2026-01-20T10:05:00Z"},
            },
        ],
    }
    with patch("boto3.client", return_value=mock_dynamo):
        result = jobs_store.list_jobs(table_name="test-jobs", region="us-east-1")
    assert len(result) == 1
    assert result[0]["job_id"] == "j1"
    assert result[0]["status"] == "completed"
    assert result[0]["s3_key"] == "uploads/v.mp4"
    assert result[0]["s3_bucket"] == "b1"
    assert result[0]["created_at"] == "2026-01-20T10:00:00Z"
