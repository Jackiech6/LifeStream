"""Unit tests for ASR processing."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

from src.models.data_models import AudioSegment
from config.settings import Settings


# Mock dependencies before importing the module
sys.modules['whisper'] = MagicMock()

from src.audio.asr import ASRProcessor


class TestASRProcessor:
    """Test ASRProcessor class."""
    
    @pytest.fixture
    def settings(self):
        """Create settings."""
        return Settings()
    
    @pytest.fixture
    def mock_audio_file(self, tmp_path):
        """Create a mock audio file path."""
        audio_file = tmp_path / "test_audio.wav"
        audio_file.touch()
        return str(audio_file)
    
    def test_merge_asr_diarization(self, settings):
        """Test merging ASR output with diarization."""
        with patch('whisper.load_model') as mock_load_model:
            mock_model = MagicMock()
            mock_load_model.return_value = mock_model
            
            processor = ASRProcessor(settings)
            
            asr_output = [
                {"start": 0.0, "end": 5.0, "text": "Hello world", "words": []},
                {"start": 5.0, "end": 10.0, "text": "How are you", "words": []},
            ]
            
            diarization_output = [
                AudioSegment(start_time=0.0, end_time=6.0, speaker_id="Speaker_01"),
                AudioSegment(start_time=6.0, end_time=10.0, speaker_id="Speaker_02"),
            ]
            
            merged = processor.merge_asr_diarization(asr_output, diarization_output)
            
            assert len(merged) == 2
            assert merged[0].transcript_text == "Hello world"
            assert merged[0].speaker_id == "Speaker_01"
            assert merged[1].transcript_text == "How are you"
            assert merged[1].speaker_id == "Speaker_02"
    
    def test_merge_asr_diarization_no_overlap(self, settings):
        """Test merging when ASR and diarization don't overlap perfectly."""
        with patch('whisper.load_model') as mock_load_model:
            mock_model = MagicMock()
            mock_load_model.return_value = mock_model
            
            processor = ASRProcessor(settings)
            
            asr_output = [
                {"start": 0.0, "end": 5.0, "text": "Hello", "words": []},
            ]
            
            diarization_output = [
                AudioSegment(start_time=6.0, end_time=10.0, speaker_id="Speaker_01"),  # No overlap
            ]
            
            merged = processor.merge_asr_diarization(asr_output, diarization_output)
            
            # Should still create segments, possibly with Speaker_Unknown
            assert len(merged) == 1
            assert merged[0].transcript_text == "Hello"
    
    def test_merge_asr_diarization_empty_asr(self, settings):
        """Test merging with empty ASR output."""
        with patch('whisper.load_model') as mock_load_model:
            mock_model = MagicMock()
            mock_load_model.return_value = mock_model
            
            processor = ASRProcessor(settings)
            
            diarization_output = [
                AudioSegment(start_time=0.0, end_time=5.0, speaker_id="Speaker_01"),
            ]
            
            merged = processor.merge_asr_diarization([], diarization_output)
            
            # Should return copy of diarization segments
            assert len(merged) == 1
            assert merged[0].speaker_id == "Speaker_01"
    
    def test_merge_asr_diarization_empty_diarization(self, settings):
        """Test merging with empty diarization output."""
        with patch('whisper.load_model') as mock_load_model:
            mock_model = MagicMock()
            mock_load_model.return_value = mock_model
            
            processor = ASRProcessor(settings)
            
            asr_output = [
                {"start": 0.0, "end": 5.0, "text": "Hello", "words": []},
            ]
            
            merged = processor.merge_asr_diarization(asr_output, [])
            
            # Should return empty list
            assert merged == []
