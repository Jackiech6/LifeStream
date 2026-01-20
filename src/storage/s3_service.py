"""S3 service for video storage and retrieval.

This module provides functions for uploading, downloading, and managing
video files in Amazon S3.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class S3UploadResult:
    """Result of an S3 upload operation."""

    success: bool
    s3_path: str
    bucket: str
    key: str
    file_size: int
    etag: Optional[str] = None
    error: Optional[str] = None


class S3Service:
    """Service for interacting with Amazon S3."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize S3Service.

        Args:
            settings: Application settings. If None, creates default settings.
        """
        self.settings = settings or Settings()
        self._check_dependencies()
        self._initialize_client()
        self._bucket_name = self._get_bucket_name()

    def _check_dependencies(self) -> None:
        """Check if boto3 is available."""
        try:
            import boto3
            logger.debug("boto3 is available")
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 operations. "
                "Install with: pip install boto3"
            )

    def _initialize_client(self) -> None:
        """Initialize boto3 S3 client."""
        try:
            import boto3

            # Use profile if specified, otherwise use default credentials
            if self.settings.aws_profile:
                session = boto3.Session(profile_name=self.settings.aws_profile)
                self.client = session.client("s3", region_name=self.settings.aws_region)
            else:
                self.client = boto3.client("s3", region_name=self.settings.aws_region)

            logger.info(f"S3 client initialized (region: {self.settings.aws_region})")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise RuntimeError(f"Could not initialize S3 client: {e}") from e

    def _get_bucket_name(self) -> str:
        """Get S3 bucket name from settings or environment."""
        if self.settings.aws_s3_bucket_name:
            return self.settings.aws_s3_bucket_name

        # Try to get from environment variable
        import os
        bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
        if bucket_name:
            return bucket_name

        raise ValueError(
            "S3 bucket name not configured. "
            "Set AWS_S3_BUCKET_NAME in environment or aws_s3_bucket_name in settings."
        )

    def upload_file(
        self,
        local_path: str | Path,
        s3_key: str,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
    ) -> S3UploadResult:
        """Upload a file to S3.

        Args:
            local_path: Path to local file to upload.
            s3_key: S3 object key (path within bucket).
            metadata: Optional metadata to attach to the object.
            content_type: Optional content type (e.g., "video/mp4").

        Returns:
            S3UploadResult with upload status and details.

        Raises:
            FileNotFoundError: If local file doesn't exist.
            RuntimeError: If upload fails.
        """
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"File not found: {local_path}")

        file_size = local_path.stat().st_size
        logger.info(f"Uploading {local_path} to s3://{self._bucket_name}/{s3_key} ({file_size} bytes)")

        try:
            import boto3
            from botocore.exceptions import ClientError

            extra_args = {}
            if metadata:
                extra_args["Metadata"] = metadata
            if content_type:
                extra_args["ContentType"] = content_type

            self.client.upload_file(
                str(local_path),
                self._bucket_name,
                s3_key,
                ExtraArgs=extra_args,
            )

            # Get object metadata to retrieve ETag
            response = self.client.head_object(Bucket=self._bucket_name, Key=s3_key)
            etag = response.get("ETag", "").strip('"')

            logger.info(f"Successfully uploaded {s3_key} (ETag: {etag})")

            return S3UploadResult(
                success=True,
                s3_path=f"s3://{self._bucket_name}/{s3_key}",
                bucket=self._bucket_name,
                key=s3_key,
                file_size=file_size,
                etag=etag,
            )

        except ClientError as e:
            error_msg = f"S3 upload failed: {e}"
            logger.error(error_msg)
            return S3UploadResult(
                success=False,
                s3_path=f"s3://{self._bucket_name}/{s3_key}",
                bucket=self._bucket_name,
                key=s3_key,
                file_size=file_size,
                error=error_msg,
            )
        except Exception as e:
            error_msg = f"Unexpected error during upload: {e}"
            logger.error(error_msg)
            return S3UploadResult(
                success=False,
                s3_path=f"s3://{self._bucket_name}/{s3_key}",
                bucket=self._bucket_name,
                key=s3_key,
                file_size=file_size,
                error=error_msg,
            )

    def download_file(
        self,
        s3_key: str,
        local_path: str | Path,
    ) -> bool:
        """Download a file from S3.

        Args:
            s3_key: S3 object key to download.
            local_path: Local path to save the file.

        Returns:
            True if download succeeded, False otherwise.

        Raises:
            RuntimeError: If download fails.
        """
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading s3://{self._bucket_name}/{s3_key} to {local_path}")

        try:
            self.client.download_file(
                self._bucket_name,
                s3_key,
                str(local_path),
            )

            file_size = local_path.stat().st_size
            logger.info(f"Successfully downloaded {s3_key} ({file_size} bytes)")
            return True

        except Exception as e:
            logger.error(f"Failed to download {s3_key}: {e}")
            raise RuntimeError(f"S3 download failed: {e}") from e

    def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600,
        http_method: str = "PUT",
    ) -> str:
        """Generate a presigned URL for direct client uploads.

        Args:
            s3_key: S3 object key.
            expiration: URL expiration time in seconds (default: 1 hour).
            http_method: HTTP method (PUT for upload, GET for download).

        Returns:
            Presigned URL string.

        Raises:
            RuntimeError: If URL generation fails.
        """
        try:
            url = self.client.generate_presigned_url(
                "put_object" if http_method == "PUT" else "get_object",
                Params={"Bucket": self._bucket_name, "Key": s3_key},
                ExpiresIn=expiration,
            )

            logger.debug(f"Generated presigned URL for {s3_key} (expires in {expiration}s)")
            return url

        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise RuntimeError(f"Presigned URL generation failed: {e}") from e

    def delete_file(self, s3_key: str) -> bool:
        """Delete a file from S3.

        Args:
            s3_key: S3 object key to delete.

        Returns:
            True if deletion succeeded, False otherwise.
        """
        try:
            self.client.delete_object(Bucket=self._bucket_name, Key=s3_key)
            logger.info(f"Deleted s3://{self._bucket_name}/{s3_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete {s3_key}: {e}")
            return False

    def file_exists(self, s3_key: str) -> bool:
        """Check if a file exists in S3.

        Args:
            s3_key: S3 object key to check.

        Returns:
            True if file exists, False otherwise.
        """
        try:
            self.client.head_object(Bucket=self._bucket_name, Key=s3_key)
            return True
        except Exception:
            return False

    def get_file_metadata(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an S3 object.

        Args:
            s3_key: S3 object key.

        Returns:
            Dictionary with metadata (size, last_modified, etag, etc.) or None if not found.
        """
        try:
            response = self.client.head_object(Bucket=self._bucket_name, Key=s3_key)
            return {
                "size": response.get("ContentLength"),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag", "").strip('"'),
                "content_type": response.get("ContentType"),
                "metadata": response.get("Metadata", {}),
            }
        except Exception as e:
            logger.warning(f"Failed to get metadata for {s3_key}: {e}")
            return None

    def list_files(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[Dict[str, Any]]:
        """List files in S3 bucket with given prefix.

        Args:
            prefix: Prefix to filter objects (e.g., "uploads/").
            max_keys: Maximum number of keys to return.

        Returns:
            List of dictionaries with key, size, last_modified, etc.
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=self._bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys,
            )

            files = []
            for obj in response.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                    "etag": obj["ETag"].strip('"'),
                })

            return files

        except Exception as e:
            logger.error(f"Failed to list files with prefix {prefix}: {e}")
            return []

    def configure_notifications(self) -> bool:
        """Configure S3 bucket notifications (typically done via Terraform).

        This method is provided for reference but notifications should be
        configured via Terraform for infrastructure-as-code best practices.

        Returns:
            True if configuration succeeded.
        """
        logger.warning(
            "S3 notifications should be configured via Terraform. "
            "This method is for reference only."
        )
        # In practice, notifications are configured in infrastructure/main.tf
        return True


__all__ = ["S3Service", "S3UploadResult"]
