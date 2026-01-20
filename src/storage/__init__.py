"""Storage module for Stage 3 cloud operations.

This module provides S3 integration for video storage and retrieval.
"""

from src.storage.s3_service import S3Service, S3UploadResult

__all__ = ["S3Service", "S3UploadResult"]
