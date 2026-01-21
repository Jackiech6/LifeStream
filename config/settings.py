"""Application settings and configuration management."""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    openai_api_key: Optional[str] = None
    huggingface_token: Optional[str] = None
    
    # Optional: Alternative LLM Provider
    anthropic_api_key: Optional[str] = None
    
    # Model Selection
    diarization_model: str = "pyannote/speaker-diarization-3.1"
    asr_model: str = "base"  # whisper model size: tiny, base, small, medium, large
    llm_model: str = "gpt-4o"  # Updated from deprecated gpt-4-vision-preview
    embedding_model_name: str = "text-embedding-3-small"
    embedding_batch_size: int = 64
    embedding_max_retries: int = 3
    
    # Processing Parameters
    scene_detection_threshold: float = 0.3
    chunk_size_seconds: int = 300  # 5 minutes
    
    # Paths (Mac-friendly, uses home directory expansion)
    # For Lambda, use /tmp (read-only file system except /tmp)
    output_dir: str = "~/LifeStream/output"  # Will be expanded to absolute path
    temp_dir: str = "~/LifeStream/temp"      # Will be expanded to absolute path
    # Speaker registry JSON file used in Stage 1/2 for nicer names in summaries
    speaker_registry_path: str = "config/speakers.json"
    
    # Mac-specific settings
    cleanup_temp_files: bool = True  # Auto-cleanup temporary files
    max_temp_file_age_hours: int = 24  # Cleanup files older than this
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None  # If None, logs only to console
    
    # AWS Configuration (Stage 3)
    aws_region: str = "us-east-1"
    aws_s3_bucket_name: Optional[str] = None  # Auto-detect from Terraform output if None
    aws_sqs_queue_url: Optional[str] = None  # Auto-detect from Terraform output if None
    aws_sqs_dlq_url: Optional[str] = None  # Dead-letter queue URL
    aws_profile: Optional[str] = None  # AWS CLI profile name (e.g., "dev")
    
    # Lambda Configuration (Stage 3.2)
    lambda_timeout: int = 900  # 15 minutes (max for Lambda)
    lambda_memory: int = 3008  # MB (max for Lambda)
    
    # Pinecone Configuration (Stage 3)
    pinecone_api_key: Optional[str] = None
    pinecone_environment: str = "us-east-1"  # Pinecone region (e.g., "us-east-1", "us-west-1-gcp")
    pinecone_index_name: str = "lifestream-dev"  # Pinecone index name
    pinecone_dimension: int = 1536  # Dimension for text-embedding-3-small
    
    # Vector Store Selection (Stage 3)
    # "auto" = automatically choose (Pinecone if API key configured, else FAISS)
    # "pinecone" = force Pinecone (requires API key)
    # "faiss" = force FAISS (local development)
    vector_store_type: str = "auto"  # auto, pinecone, or faiss
    vector_store_index_dir: str = "memory_index"  # Directory for FAISS index
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Lambda environment detection: if AWS_LAMBDA_FUNCTION_NAME is set, use /tmp
        import os
        if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            # Lambda environment: use /tmp (only writable location)
            self.output_dir = "/tmp/lifestream/output"
            self.temp_dir = "/tmp/lifestream/temp"
        else:
            # Local development: expand user paths
            self.output_dir = str(Path(self.output_dir).expanduser())
            self.temp_dir = str(Path(self.temp_dir).expanduser())
        
        # Create directories if they don't exist (skip in Lambda if path not writable)
        try:
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            # Lambda: directories will be created per-job in /tmp
            pass
        
        # Create log file directory if specified
        if self.log_file:
            try:
                log_path = Path(self.log_file).expanduser()
                log_path.parent.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError):
                # Lambda: skip log file creation if not writable
                pass
