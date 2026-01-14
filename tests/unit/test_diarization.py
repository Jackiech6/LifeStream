"""Unit tests for speaker diarization."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

from src.models.data_models import AudioSegment
from config.settings import Settings


# Mock dependencies before importing the module
sys.modules['torch'] = MagicMock()
sys.modules['pyannote'] = MagicMock()
sys.modules['pyannote.audio'] = MagicMock()
sys.modules['pyannote.audio'].Pipeline = MagicMock

from src.audio.diarization import SpeakerDiarizer


class TestSpeakerDiarizer:
    """Test SpeakerDiarizer class."""
    
    @pytest.fixture
    def settings(self):
        """Create settings with mock token."""
        settings = Settings()
        settings.huggingface_token = "mock_token"
        settings.diarization_model = "pyannote/speaker-diarization-3.1"
        return settings
    
    @pytest.fixture
    def mock_audio_file(self, tmp_path):
        """Create a mock audio file path."""
        audio_file = tmp_path / "test_audio.wav"
        audio_file.touch()
        return str(audio_file)
    
    @patch('pyannote.audio.Pipeline')
    def test_merge_overlapping_segments(self, mock_pipeline_class, settings):
        """Test merging overlapping segments."""
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline
        
        # Configure mocked torch
        mock_torch = sys.modules['torch']
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends = MagicMock()
        mock_torch.backends.mps = MagicMock()
        mock_torch.backends.mps.is_available.return_value = False
        mock_torch.device.return_value = "cpu"
        
        diarizer = SpeakerDiarizer(settings)
        
        segments = [
            AudioSegment(start_time=0.0, end_time=5.0, speaker_id="Speaker_01"),
            AudioSegment(start_time=4.0, end_time=8.0, speaker_id="Speaker_02"),  # Overlaps
            AudioSegment(start_time=9.0, end_time=12.0, speaker_id="Speaker_01"),
        ]
        
        merged = diarizer.merge_overlapping_segments(segments)
        
        # Should have fewer or equal segments
        assert len(merged) <= len(segments)
        assert all(isinstance(s, AudioSegment) for s in merged)
        # All segments should have valid time ranges
        assert all(s.start_time < s.end_time for s in merged)
    
    @patch('pyannote.audio.Pipeline')
    def test_merge_overlapping_segments_empty(self, mock_pipeline_class, settings):
        """Test merging with empty segments."""
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline
        
        # Configure mocked torch
        mock_torch = sys.modules['torch']
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends = MagicMock()
        mock_torch.backends.mps = MagicMock()
        mock_torch.backends.mps.is_available.return_value = False
        mock_torch.device.return_value = "cpu"
        
        diarizer = SpeakerDiarizer(settings)
        
        merged = diarizer.merge_overlapping_segments([])
        assert merged == []
    
    @patch('pyannote.audio.Pipeline')
    def test_merge_overlapping_segments_no_overlap(self, mock_pipeline_class, settings):
        """Test merging segments with no overlap."""
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline
        
        # Configure mocked torch
        mock_torch = sys.modules['torch']
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends = MagicMock()
        mock_torch.backends.mps = MagicMock()
        mock_torch.backends.mps.is_available.return_value = False
        mock_torch.device.return_value = "cpu"
        
        diarizer = SpeakerDiarizer(settings)
        
        segments = [
            AudioSegment(start_time=0.0, end_time=5.0, speaker_id="Speaker_01"),
            AudioSegment(start_time=5.0, end_time=10.0, speaker_id="Speaker_02"),  # No overlap
            AudioSegment(start_time=10.0, end_time=15.0, speaker_id="Speaker_01"),
        ]
        
        merged = diarizer.merge_overlapping_segments(segments)
        
        # Should have same number of segments
        assert len(merged) == len(segments)
        assert all(isinstance(s, AudioSegment) for s in merged)
