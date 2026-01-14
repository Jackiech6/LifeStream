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
    
    # Processing Parameters
    scene_detection_threshold: float = 0.3
    chunk_size_seconds: int = 300  # 5 minutes
    
    # Paths (Mac-friendly, uses home directory expansion)
    output_dir: str = "~/LifeStream/output"  # Will be expanded to absolute path
    temp_dir: str = "~/LifeStream/temp"      # Will be expanded to absolute path
    
    # Mac-specific settings
    cleanup_temp_files: bool = True  # Auto-cleanup temporary files
    max_temp_file_age_hours: int = 24  # Cleanup files older than this
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None  # If None, logs only to console
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Expand user paths on Mac
        self.output_dir = str(Path(self.output_dir).expanduser())
        self.temp_dir = str(Path(self.temp_dir).expanduser())
        # Create directories if they don't exist
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        
        # Create log file directory if specified
        if self.log_file:
            log_path = Path(self.log_file).expanduser()
            log_path.parent.mkdir(parents=True, exist_ok=True)
