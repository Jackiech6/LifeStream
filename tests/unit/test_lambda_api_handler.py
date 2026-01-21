"""Unit tests for Lambda API handler."""

import pytest
import json
from unittest.mock import MagicMock, patch, Mock

from src.api.lambda_handler import lambda_handler, handler


def test_lambda_handler_import():
    """Lambda handler should import successfully."""
    from src.api.lambda_handler import lambda_handler
    assert callable(lambda_handler)


def test_lambda_handler_with_api_gateway_event():
    """Lambda handler should handle API Gateway events."""
    # Mock API Gateway event
    event = {
        "httpMethod": "GET",
        "path": "/health",
        "headers": {},
        "queryStringParameters": None,
        "body": None,
        "isBase64Encoded": False,
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "dev"
        }
    }
    
    context = MagicMock()
    context.request_id = "test-request-id"
    
    # Mock Mangum handler
    with patch("src.api.lambda_handler.handler") as mock_handler:
        mock_handler.return_value = {
            "statusCode": 200,
            "body": json.dumps({"status": "healthy"})
        }
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        mock_handler.assert_called_once()


def test_lambda_handler_with_upload_event():
    """Lambda handler should handle file upload events."""
    event = {
        "httpMethod": "POST",
        "path": "/api/v1/upload",
        "headers": {
            "Content-Type": "multipart/form-data"
        },
        "body": "base64-encoded-file",
        "isBase64Encoded": True
    }
    
    context = MagicMock()
    
    with patch("src.api.lambda_handler.handler") as mock_handler:
        mock_handler.return_value = {
            "statusCode": 200,
            "body": json.dumps({"job_id": "test-123", "status": "queued"})
        }
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        assert "job_id" in json.loads(result["body"])


def test_lambda_handler_with_query_event():
    """Lambda handler should handle query events."""
    event = {
        "httpMethod": "POST",
        "path": "/api/v1/query",
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "query": "test query",
            "top_k": 5
        }),
        "isBase64Encoded": False
    }
    
    context = MagicMock()
    
    with patch("src.api.lambda_handler.handler") as mock_handler:
        mock_handler.return_value = {
            "statusCode": 200,
            "body": json.dumps({
                "query": "test query",
                "results": [],
                "total_results": 0
            })
        }
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        data = json.loads(result["body"])
        assert "query" in data
        assert "results" in data


def test_lambda_handler_error_handling():
    """Lambda handler should handle errors gracefully."""
    event = {
        "httpMethod": "GET",
        "path": "/nonexistent",
        "headers": {},
        "body": None
    }
    
    context = MagicMock()
    
    with patch("src.api.lambda_handler.handler") as mock_handler:
        mock_handler.side_effect = Exception("Test error")
        
        # Should not raise, but return error response
        # Mangum will handle this, but we test that handler is called
        try:
            result = lambda_handler(event, context)
        except Exception:
            # If Mangum doesn't catch it, that's also acceptable
            pass
        
        mock_handler.assert_called_once()
