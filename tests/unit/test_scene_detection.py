"""Unit tests for scene detection."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

from src.models.data_models import VideoFrame
from config.settings import Settings

from src.video.scene_detection import SceneDetector


class TestSceneDetector:
    """Test SceneDetector class."""
    
    @pytest.fixture
    def settings(self):
        """Create settings."""
        return Settings()
    
    @pytest.fixture
    def mock_video_file(self, tmp_path):
        """Create a mock video file path."""
        video_file = tmp_path / "test_video.mp4"
        video_file.touch()
        return str(video_file)
    
    
    def test_detect_scene_changes_nonexistent_file(self, settings):
        """Test scene detection with non-existent file."""
        detector = SceneDetector(settings)
        
        with pytest.raises(ValueError, match="Video file does not exist"):
            detector.detect_scene_changes("/nonexistent/file.mp4")
    
    def test_extract_keyframes_nonexistent_file(self, settings):
        """Test keyframe extraction with non-existent file."""
        detector = SceneDetector(settings)
        
        with pytest.raises(ValueError, match="Video file does not exist"):
            detector.extract_keyframes("/nonexistent/file.mp4", [5.0])
